#!/usr/bin/env python3.9
"""
DeFi Risk Assessment System Tray
Enhanced system tray with window management and complete functionality
Runs as background process to avoid duplicate dock icons
"""

import os
import sys

# macOS specific environment setup
if sys.platform == "darwin":
    # Basic macOS environment variables
    os.environ['LSUIElement'] = 'true'
    os.environ['NSApplicationActivationPolicy'] = 'accessory'
    os.environ['PYTHONUNBUFFERED'] = '1'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

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
    try:
        # Try importing from current directory
        import sys
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        from tkinter_compatibility import tkinter_compat
        print("✅ Tkinter compatibility module imported (local)")
    except Exception as e2:
        print(f"⚠️ Tkinter compatibility import error (local): {e2}")
        tkinter_compat = None

# NOW import other modules after macOS compatibility is set up
import time
import subprocess
import threading
import tempfile
import signal
import json
import hashlib
import hmac
import fcntl
from typing import Any, cast

from system_update_manager import (
    DEFAULT_SYSTEM_UPDATE_SETTINGS,
    REQUIREMENTS_FILE,
    check_outdated_packages,
    install_requirements_upgrade,
    load_update_state,
    run_pip_check,
    run_safety_dry_run,
    save_update_state,
    should_run_auto_check,
    utc_now_iso,
)

# CRITICAL: Import PIL with fallback handling
PIL_AVAILABLE = False
Image = None
ImageDraw = None

try:
    # Use importlib for better linter compatibility
    import importlib
    pil_module = importlib.import_module('PIL.Image')
    draw_module = importlib.import_module('PIL.ImageDraw')
    Image = pil_module
    ImageDraw = draw_module.Draw
    PIL_AVAILABLE = True
    print("✅ PIL (Pillow) imported successfully")
except (ImportError, AttributeError) as e:
    print(f"⚠️ PIL import error: {e}")
    PIL_AVAILABLE = False
    # Create fallback Image and ImageDraw classes
    class FallbackImage:
        def __init__(self, mode='RGB', size=(64, 64), color='#2c3e50'):
            self.mode = mode
            self.size = size
            self.color = color
        
        def save(self, *args, **kwargs):
            pass  # No-op for fallback
    
    class FallbackImageDraw:
        def __init__(self, image):
            self.image = image
        
        def ellipse(self, *args, **kwargs):
            pass  # No-op for fallback
        
        def line(self, *args, **kwargs):
            pass  # No-op for fallback
    
    Image = FallbackImage
    ImageDraw = FallbackImageDraw

# CRITICAL: Import pystray with fallback handling
PYSTRAY_AVAILABLE = False
pystray = None
item = None

try:
    # Use importlib for better linter compatibility
    import importlib
    pystray = importlib.import_module('pystray')
    item = cast(Any, pystray).MenuItem
    PYSTRAY_AVAILABLE = True
    print("✅ pystray imported successfully")
except ImportError as e:
    print(f"⚠️ pystray import error: {e}")
    PYSTRAY_AVAILABLE = False
    # Create fallback pystray classes
    class FallbackIcon:
        def __init__(self, name, image, title, menu):
            self.name = name
            self.title = title
            self.menu = menu
        
        def run(self):
            print("⚠️ System tray not available - running in console mode")
            while True:
                time.sleep(1)
        
        def stop(self):
            pass
        
        def notify(self, message, title):
            print(f"Notification ({title}): {message}")
    
    class FallbackMenu:
        def __init__(self, *items):
            self.items = items
    
    class FallbackMenuItem:
        def __init__(self, text, action, default=False, enabled=True):
            self.text = text
            self.action = action
            self.default = default
            self.enabled = enabled
    
    # Create a mock pystray module
    class MockPystray:
        Icon = FallbackIcon
        Menu = FallbackMenu
        MenuItem = FallbackMenuItem
        SEPARATOR = "---"
    
    pystray = MockPystray()
    item = FallbackMenuItem

# Separator sentinel for menus
try:
    TRAY = cast(Any, pystray)
    SEPARATOR = getattr(TRAY, 'SEPARATOR', getattr(getattr(TRAY, 'Menu', None), 'SEPARATOR', None))
except Exception:
    SEPARATOR = "---"

# Ensure item is treated as callable for type checker
item = cast(Any, item)

# CRITICAL: Import process manager with tkinter compatibility
try:
    from process_manager import process_manager
    print("✅ Process manager imported successfully")
except Exception as e:
    print(f"⚠️ Process manager import error: {e}")
    try:
        # Try importing from current directory
        import sys
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        from process_manager import process_manager
        print("✅ Process manager imported successfully (local)")
    except Exception as e2:
        print(f"⚠️ Process manager import error (local): {e2}")
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

        # No-op stubs to satisfy type checker for fallbacks
        def _is_service_running(self, name: str) -> bool:
            return False

        def _bring_window_to_front(self, name: str) -> None:
            return None

        def launch_status(self):
            return True, "Status launched"

        def launch_settings(self):
            return True, "Settings launched"

        def force_cleanup_stale_processes(self):
            return True

        def force_refresh_status(self):
            return True

        def cleanup_all_stale_locks(self):
            return True

        def launch_about(self):
            return True, "About launched"

        def terminate_service(self, name: str):
            return True
    
    process_manager = MinimalProcessManager()
    print("✅ Using minimal process manager")

# Set up macOS environment for system tray
if sys.platform == "darwin":
    
    
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
    
    print("✅ Environment variables set")
    print("Running system tray")

# Project paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DASHBOARD_PATH = os.path.join(os.path.dirname(__file__), 'defi_dashboard.py')
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
        signature = hmac.digest(
            WEBHOOK_SHARED_SECRET.encode('utf-8'),
            signed_payload,
            'sha3_256',
        ).hex()
        headers['X-Webhook-Timestamp'] = timestamp
        headers['X-Webhook-Signature'] = f'sha3_256={signature}'
        headers['Content-Type'] = 'application/json'
    return headers

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
        self._cache_refresh_state_lock = threading.Lock()
        self._cache_refresh_inflight = False
        self._cache_refresh_error_cooldown_s = 120.0
        self._cache_refresh_last_error_ts = 0.0
        self.system_update_thread = None
        self._system_update_lock = threading.Lock()
        self._system_update_inflight = False
        
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
        
        # Bring window to front on startup (configurable)
        if not self._is_focus_disabled():
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
        
        # Start webhook server automatically
        self.start_webhook_server()
        # Start dependency update monitor (low-frequency and safe-check aware)
        self.start_system_update_monitor()

    @staticmethod
    def _parse_duration_to_hours(value, default_hours=24.0):
        """Parse duration strings such as '15 minutes', '2 hours', or '30 days'."""
        try:
            if isinstance(value, (int, float)):
                parsed = float(value)
                return parsed if parsed > 0 else float(default_hours)
            text = str(value or '').strip().lower()
            if not text:
                return float(default_hours)
            amount_token = ''.join(ch for ch in text if ch.isdigit() or ch == '.')
            if not amount_token:
                return float(default_hours)
            amount = float(amount_token)
            if 'minute' in text:
                return max(1.0 / 60.0, amount / 60.0)
            if 'day' in text:
                return amount * 24.0
            if 'week' in text:
                return amount * 24.0 * 7.0
            if 'month' in text:
                return amount * 24.0 * 30.0
            if 'year' in text:
                return amount * 24.0 * 365.0
            return amount
        except Exception:
            return float(default_hours)

    def _load_cache_settings_policy(self):
        """Load cache interval/retention policy from shared settings.json."""
        policy = {
            'interval_hours': 1.0,
            'retention_hours': 24.0,
        }
        try:
            settings_file = os.path.join(self.project_root, 'data', 'settings.json')
            if not os.path.exists(settings_file):
                return policy
            with open(settings_file, 'r') as f:
                settings = json.load(f) or {}
            cache_cfg = settings.get('cache', {}) if isinstance(settings, dict) else {}

            interval_text = cache_cfg.get('auto_refresh_interval', '1 hour')
            retention_text = cache_cfg.get('cache_retention', '24 hours')
            interval_h = self._parse_duration_to_hours(interval_text, 1.0)
            retention_h = self._parse_duration_to_hours(retention_text, 24.0)

            custom_days = cache_cfg.get('cache_retention_custom_days')
            if custom_days not in (None, ''):
                try:
                    retention_h = max(retention_h, float(custom_days) * 24.0)
                except Exception:
                    pass

            policy['interval_hours'] = max(1.0 / 60.0, min(interval_h, 24.0 * 365.0))
            policy['retention_hours'] = max(1.0, min(retention_h, 24.0 * 365.0))
        except Exception as e:
            print(f"⚠️ Could not load cache policy settings: {e}")
        return policy

    def _load_system_update_policy(self):
        """Load system-update configuration from shared settings.json."""
        policy = dict(DEFAULT_SYSTEM_UPDATE_SETTINGS)
        try:
            settings_file = os.path.join(self.project_root, 'data', 'settings.json')
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    settings = json.load(f) or {}
                if isinstance(settings, dict):
                    loaded = settings.get('system_update', {})
                    if isinstance(loaded, dict):
                        policy.update(loaded)
        except Exception as e:
            print(f"⚠️ Could not load system update policy: {e}")
        return policy

    def start_system_update_monitor(self):
        """Run scheduled dependency check/install cycle in background tray process."""
        if self.system_update_thread and self.system_update_thread.is_alive():
            return

        def _monitor():
            print("🧰 System update monitor thread started")
            while True:
                try:
                    self._run_scheduled_system_update_cycle()
                except Exception as e:
                    print(f"⚠️ System update monitor error: {e}")
                time.sleep(300)  # every 5 minutes

        self.system_update_thread = threading.Thread(target=_monitor, daemon=True)
        self.system_update_thread.start()

    def _run_scheduled_system_update_cycle(self):
        """Evaluate schedule and run safe dependency update if due."""
        with self._system_update_lock:
            if self._system_update_inflight:
                return
            self._system_update_inflight = True
        try:
            policy = self._load_system_update_policy()
            state = load_update_state()
            if not should_run_auto_check(policy, state):
                return

            print("🧰 Running scheduled dependency check...")
            check = check_outdated_packages(timeout_seconds=300)
            state["last_check_at"] = utc_now_iso()
            state["last_check_duration_seconds"] = float(check.get("duration_seconds", 0.0) or 0.0)
            state["last_check_output_tail"] = (
                (check.get("stdout_tail") or "")
                + ("\n" + check.get("stderr_tail") if check.get("stderr_tail") else "")
            ).strip()

            if not bool(check.get("ok", False)):
                state["last_check_status"] = "failed"
                state["last_error"] = str(check.get("error", "Unknown check error"))
                save_update_state(state)
                print(f"⚠️ Dependency check failed: {state['last_error']}")
                return

            packages = check.get("packages", []) or []
            state["last_outdated_packages"] = packages
            state["last_outdated_count"] = len(packages)
            state["last_error"] = ""
            if not packages:
                state["last_check_status"] = "up_to_date"
                save_update_state(state)
                print("✅ Dependencies are up to date")
                return

            state["last_check_status"] = "updates_available"
            save_update_state(state)
            if not bool(policy.get("auto_install_safe_updates", False)):
                print(f"ℹ️ {len(packages)} dependency updates available (auto-install disabled)")
                return

            timeout_seconds = int(policy.get("max_update_timeout_seconds", 1800) or 1800)
            if bool(policy.get("safety_check_enabled", True)):
                safety = run_safety_dry_run(
                    requirements_path=REQUIREMENTS_FILE,
                    timeout_seconds=min(timeout_seconds, 900),
                )
                if not bool(safety.get("ok", False)):
                    state["last_update_status"] = "blocked_by_safety_check"
                    state["last_error"] = str(safety.get("error", "Safety dry-run failed"))
                    state["last_update_output_tail"] = (
                        (safety.get("stdout_tail") or "")
                        + ("\n" + safety.get("stderr_tail") if safety.get("stderr_tail") else "")
                    ).strip()
                    save_update_state(state)
                    print("⚠️ Dependency update blocked by safety check")
                    return

            install = install_requirements_upgrade(
                requirements_path=REQUIREMENTS_FILE,
                timeout_seconds=timeout_seconds,
            )
            if not bool(install.get("ok", False)):
                state["last_update_status"] = "failed"
                state["last_error"] = str(install.get("error", "Install failed"))
                state["last_update_duration_seconds"] = float(install.get("duration_seconds", 0.0) or 0.0)
                state["last_update_output_tail"] = (
                    (install.get("stdout_tail") or "")
                    + ("\n" + install.get("stderr_tail") if install.get("stderr_tail") else "")
                ).strip()
                save_update_state(state)
                print("⚠️ Dependency install failed")
                return

            verify = run_pip_check()
            state["last_update_at"] = utc_now_iso()
            state["last_update_duration_seconds"] = float(install.get("duration_seconds", 0.0) or 0.0)
            state["last_update_output_tail"] = (
                (install.get("stdout_tail") or "")
                + ("\n" + install.get("stderr_tail") if install.get("stderr_tail") else "")
            ).strip()

            # Refresh outdated counts after install so UI/state don't stay stale.
            post_check = check_outdated_packages(timeout_seconds=300)
            if bool(post_check.get("ok", False)):
                remaining = post_check.get("packages", []) or []
                state["last_check_at"] = utc_now_iso()
                state["last_check_duration_seconds"] = float(post_check.get("duration_seconds", 0.0) or 0.0)
                state["last_check_output_tail"] = (
                    (post_check.get("stdout_tail") or "")
                    + ("\n" + post_check.get("stderr_tail") if post_check.get("stderr_tail") else "")
                ).strip()
                state["last_outdated_packages"] = remaining
                state["last_outdated_count"] = len(remaining)
                state["last_check_status"] = "up_to_date" if not remaining else "updates_available"
            else:
                remaining = state.get("last_outdated_packages", []) or []
                state["last_check_status"] = "failed"
                state["last_error"] = str(post_check.get("error", state.get("last_error", "")))
            if bool(verify.get("ok", False)):
                state["last_update_status"] = "success"
                state["last_error"] = ""
                if remaining:
                    print(f"✅ Dependency auto-update applied ({len(packages)} package(s)); {len(remaining)} update(s) still pending")
                else:
                    print(f"✅ Dependency auto-update applied ({len(packages)} package(s)); no pending updates remain")
            else:
                state["last_update_status"] = "installed_with_warnings"
                state["last_error"] = str(verify.get("error", "pip check warnings"))
                state["last_update_output_tail"] = (
                    state.get("last_update_output_tail", "")
                    + "\n"
                    + (verify.get("stdout_tail") or "")
                    + ("\n" + verify.get("stderr_tail") if verify.get("stderr_tail") else "")
                ).strip()
                print("⚠️ Dependency update installed with pip-check warnings")
            save_update_state(state)
        finally:
            with self._system_update_lock:
                self._system_update_inflight = False

    @staticmethod
    def _cache_has_missing_metrics(cache_data):
        """Return True if any token still misses core key metrics."""
        try:
            tokens = (cache_data or {}).get('tokens', {})
            if not isinstance(tokens, dict) or not tokens:
                return True
            for token_blob in tokens.values():
                if not isinstance(token_blob, dict):
                    return True
                market_cap = float(token_blob.get('market_cap') or 0)
                volume_24h = float(token_blob.get('volume_24h') or 0)
                holders = float(token_blob.get('holders') or 0)
                liquidity = float(token_blob.get('liquidity') or 0)
                if market_cap <= 0 or volume_24h <= 0 or holders <= 0 or liquidity <= 0:
                    return True
            return False
        except Exception:
            return True
    
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
    
    def _create_unified_environment(self):
        """Create environment variables for unified app icon across all subprocesses"""
        env = os.environ.copy()
        env['PYTHONPATH'] = os.path.join(self.project_root, 'scripts', 'v2.0')
        
        # macOS specific environment variables for unified app icon
        if sys.platform == "darwin":
            # Unified app icon environment variables with CORRECT bundle identifier
            env['BUNDLE_IDENTIFIER'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
            env['APP_BUNDLE'] = 'true'
            env['CFBundleIdentifier'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
            env['CFBundleName'] = 'Token Risk Assessment Tool'
            env['CFBundleDisplayName'] = 'Token Risk Assessment Tool'
            env['PARENT_BUNDLE_ID'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
            env['INHERIT_BUNDLE_ID'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
            
            # Performance optimizations
            env['PYTHONUNBUFFERED'] = '1'
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            
            # Set activation policy for background operation
            env['NSApplicationActivationPolicy'] = 'accessory'
            env['LSUIElement'] = 'true'
            
            # Additional macOS environment variables
            env['NSDocumentRevisionsKeepEveryOne'] = '1'
            env['NSAppTransportSecurity'] = 'true'
            
            # Force basic mode and skip all macOS checks
            env['TK_FORCE_BASIC_MODE'] = '1'
            env['TK_SKIP_ALL_MACOS_CHECKS'] = '1'
            env['TK_DISABLE_ALL_MACOS_FEATURES'] = '1'
            env['TK_DISABLE_MACOS_VERSION_CALLS'] = '1'
            env['TK_SKIP_MACOS_VERSION_CHECK'] = '1'
            env['TK_DISABLE_MACOS_VERSION_METHOD'] = '1'
            env['TK_USE_LEGACY_MODE'] = '1'
            env['TK_DISABLE_NATIVE_FEATURES'] = '1'
            env['TK_FORCE_COMPATIBILITY_MODE'] = '1'
            
            # Tkinter compatibility
            env['TK_SILENCE_DEPRECATION'] = '1'
            env['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
            env['TK_FRAMEWORK'] = '1'
            env['DISPLAY'] = ':0'
            
            # Force unified app icon
            env['NSApplicationActivationPolicy'] = 'accessory'
            env['LSUIElement'] = 'true'
            env['NSWindowCollectionBehavior'] = 'NSWindowCollectionBehaviorParticipatesInCycle'
            env['NSWindowLevel'] = 'Normal'
            
            # Additional variables to prevent Python icon from showing
            env['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
            env['TK_FRAMEWORK'] = '1'
            env['TK_SILENCE_DEPRECATION'] = '1'
            env['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
            env['TK_FRAMEWORK'] = '1'
            env['TK_SILENCE_DEPRECATION'] = '1'
        
        return env
    
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
        if self._is_focus_disabled():
            print("ℹ️ Skipping bring-to-front (focus disabled)")
            return
        try:
            import subprocess
            
            # Enhanced AppleScript to bring windows to front with better detection
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
                                -- More comprehensive window name matching
                                if windowName contains "DeFi" or windowName contains "Risk" or windowName contains "Assessment" or windowName contains "Credential" or windowName contains "Dashboard" or windowName contains "Settings" or windowName contains "About" or windowName contains "API" or windowName contains "Chain" or windowName contains "Chain ID" or windowName contains "System Tray" or windowName contains "Token" then
                                    set frontmost of appProcess to true
                                    perform action "AXRaise" of windowItem
                                    return "Found and raised window: " & windowName
                                end if
                            end repeat
                        end tell
                    end try
                end repeat
                
                -- Also check for any application with "DeFi" or "Risk" in the name
                set allProcesses to every application process
                repeat with appProcess in allProcesses
                    try
                        set processName to name of appProcess
                        if processName contains "DeFi" or processName contains "Risk" or processName contains "Assessment" then
                            tell appProcess
                                if exists (window 1) then
                                    set frontmost of appProcess to true
                                    set windowList to every window
                                    repeat with windowItem in windowList
                                        perform action "AXRaise" of windowItem
                                    end repeat
                                    return "Brought " & processName & " to front"
                                end if
                            end tell
                        end if
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
        # Check if PIL is available
        if not PIL_AVAILABLE:
            print("⚠️ PIL not available, using fallback icon")
            image = self._create_generated_icon()
        else:
            # Try multiple icon paths in order of preference (prefer PNG for pystray/Pillow)
            tray_icon_path = os.getenv('TRAY_ICON_PATH', '')
            print(f"🔍 TRAY_ICON_PATH from env: '{tray_icon_path}'")
            icon_paths = [
                tray_icon_path,
                os.path.join(PROJECT_ROOT, 'docs', 'Logos', 'crypto_tiny.png'),
                os.path.join(PROJECT_ROOT, 'docs', 'Logos', 'crypto_small.png'),
                os.path.join(PROJECT_ROOT, 'docs', 'Logos', 'crypto.png'),
                os.path.join(PROJECT_ROOT, 'docs', 'Logos', 'crypto.icns'),
                os.path.join(PROJECT_ROOT, 'DeFi Risk Assessment.app', 'Contents', 'Resources', 'crypto.icns'),
                os.path.join(PROJECT_ROOT, 'docs', 'Logos', 'magnifier_tray.ico'),
                os.path.join(PROJECT_ROOT, 'docs', 'Logos', 'app_icon_tray.ico')
            ]
            print(f"🔍 Icon paths to try: {[p for p in icon_paths if p]}")
            
            image = None
            for i, icon_path in enumerate(icon_paths):
                if icon_path and os.path.exists(icon_path):
                    print(f"🔍 Trying icon {i+1}: {icon_path}")
                    try:
                        img_mod = cast(Any, Image)
                        image = img_mod.open(icon_path)
                        print(f"✅ Using icon from: {icon_path}")
                        break
                    except Exception as e:
                        print(f"❌ Failed to load icon from: {icon_path}")
                        print(f"⚠️ Could not load icon from {icon_path}: {e}")
                        continue
                elif icon_path:
                    print(f"❌ Icon path does not exist: {icon_path}")
            
            if image is None:
                print("⚠️ No icons found, using generated icon")
                image = self._create_generated_icon()
        
        # Create dynamic menu that shows running services
        self.menu = self.create_dynamic_menu()
        
        tray = cast(Any, pystray)
        self.icon = tray.Icon("DeFi Risk Assessment", image, "DeFi Risk Assessment Tool", self.menu)
        print("✅ System tray icon created successfully")
        print("✅ Dynamic menu configured")
    
    def _create_generated_icon(self):
        """Create a generated magnifier icon as fallback"""
        if not PIL_AVAILABLE:
            # Return a simple fallback image object
            img_cls = cast(Any, Image)
            return img_cls(mode='RGB', size=(64, 64), color='#2c3e50')
        
        # Create a clean, high-quality magnifier icon
        img_mod = cast(Any, Image)
        draw_mod = cast(Any, ImageDraw)
        image = img_mod.new('RGB', (64, 64), color='#2c3e50')
        draw = draw_mod.Draw(image)
        
        # Draw a clean magnifier icon
        # Magnifier glass (circle)
        draw.ellipse([12, 12, 44, 44], fill='#3498db', outline='#ffffff', width=2)
        # Magnifier handle
        draw.line([44, 44, 52, 52], fill='#ffffff', width=3)
        # Magnifier lens highlight
        draw.ellipse([18, 18, 26, 26], fill='#ffffff', outline='#3498db', width=1)
        
        return image
    

    
    def create_dynamic_menu(self):
        """Create dynamic menu that shows running services"""
        menu_items = []
        from typing import cast, Any as _Any
        menu_item = cast(_Any, item)
        
        # Add running services section
        running_services = self.get_running_services()
        if running_services:
            menu_items.append(SEPARATOR)
            menu_items.append(menu_item("🖥️ Running Services:", None, enabled=False))
            for service_name, window_title in running_services:
                menu_items.append(menu_item(f"  📋 {service_name}", 
                                     lambda s=service_name, w=window_title: self.bring_service_to_front(s, w)))
            menu_items.append(SEPARATOR)
        
        # Add main menu items
        menu_items.extend([
            menu_item('🚀 Quick Assessment', self.quick_assessment),
            SEPARATOR,
            menu_item('📊 Open Main Dashboard', self.open_dashboard, default=True),
            menu_item('🔧 API Service Dashboard', self.open_api_dashboard),
            SEPARATOR,
            menu_item('🔐 Manage Credentials', self.manage_credentials),
            menu_item('🔗 Manage Chains', self.manage_chains),
            menu_item('🔄 Refresh Cache', self.manual_cache_refresh),
            menu_item('📋 View Reports', self.view_reports),
            menu_item('📈 Check Status', self.check_status),
            SEPARATOR,
            menu_item('🧹 Force Cleanup', self.force_cleanup),
            menu_item('⚙️ Settings', self.open_settings),
            menu_item('ℹ️ About', self.show_about),
            SEPARATOR,
            menu_item('❌ Quit', self.quit_application)
        ])
        
        tray = cast(_Any, pystray)
        return tray.Menu(*menu_items)
    
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
        if self._is_focus_disabled():
            print(f"ℹ️ Skipping bring-to-front for '{window_title}' (focus disabled)")
            return
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

    def _is_focus_disabled(self):
        """Return True if focus/bring-to-front is disabled by config/env."""
        mode = os.getenv('FOCUS_BEHAVIOR', 'disabled').lower()
        return mode in ("disabled", "off", "false", "0")
    
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
    
    def start_webhook_server(self):
        """Start webhook server automatically"""
        try:
            # Check if webhook server is already running
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', 5001))
            sock.close()
            
            if result == 0:
                print("✅ Webhook server already running on port 5001")
                try:
                    print("🔄 Triggering background cache enrichment on startup...")
                    self.trigger_cache_refresh()
                except Exception as refresh_err:
                    print(f"⚠️ Startup cache enrichment trigger failed: {refresh_err}")
                return
            
            # Start webhook server (use v2.0 implementation)
            webhook_script = os.path.join(self.project_root, 'scripts', 'v2.0', 'webhook_server.py')
            if os.path.exists(webhook_script):
                print("🚀 Starting webhook server...")
                env = self._create_unified_environment()
                
                # Start webhook server in background
                self.webhook_process = subprocess.Popen(
                    [sys.executable, webhook_script],
                    env=env,
                    cwd=self.project_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # Wait a moment for server to start
                time.sleep(2)
                
                # Check if server started successfully
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(('localhost', 5001))
                sock.close()
                
                if result == 0:
                    print("✅ Webhook server started successfully")
                    try:
                        print("🔄 Triggering initial background cache enrichment...")
                        self.trigger_cache_refresh()
                    except Exception as refresh_err:
                        print(f"⚠️ Initial cache enrichment trigger failed: {refresh_err}")
                else:
                    print("⚠️ Webhook server may not have started properly")
            else:
                print("⚠️ Webhook server script not found")
                
        except Exception as e:
            print(f"❌ Error starting webhook server: {e}")
    

    
    def check_and_refresh_cache(self):
        """Check cache age and refresh if needed using settings retention policy."""
        try:
            cache_file = os.path.join(PROJECT_ROOT, 'data', 'real_data_cache.json')
            policy = self._load_cache_settings_policy()
            interval_hours = float(policy.get('interval_hours', 1.0))
            retention_hours = float(policy.get('retention_hours', 24.0))
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                last_updated = cache_data.get('last_updated', 0)
                cache_age_hours = (time.time() - last_updated) / 3600
                has_missing_values = self._cache_has_missing_metrics(cache_data)

                should_refresh = False
                refresh_reason = ""
                if cache_age_hours >= retention_hours:
                    should_refresh = True
                    refresh_reason = (
                        f"stale by retention ({cache_age_hours:.1f}h >= {retention_hours:.1f}h)"
                    )
                elif has_missing_values and cache_age_hours >= interval_hours:
                    should_refresh = True
                    refresh_reason = (
                        f"incremental fill for missing values "
                        f"({cache_age_hours:.1f}h >= {interval_hours:.2f}h)"
                    )

                if should_refresh:
                    print(f"Cache refresh triggered: {refresh_reason}")
                    self.trigger_cache_refresh()
                else:
                    print(
                        f"Cache is fresh ({cache_age_hours:.1f} hours old) | "
                        f"retention={retention_hours:.1f}h | "
                        f"missing_values={'yes' if has_missing_values else 'no'}"
                    )
            else:
                print("No cache file found, triggering initial refresh...")
                self.trigger_cache_refresh()
        except Exception as e:
            print(f"Error checking cache: {e}")
    
    def trigger_cache_refresh(self):
        """Trigger cache refresh via webhook (fire-and-forget to avoid UI blocking)"""
        try:
            import requests
            import socket
            import threading
            with self._cache_refresh_state_lock:
                if self._cache_refresh_inflight:
                    print("⏭️ Cache refresh already in progress; skipping duplicate trigger")
                    return
                self._cache_refresh_inflight = True

            # First check if webhook server is running
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            result = sock.connect_ex(('localhost', 5001))
            sock.close()

            if result != 0:
                print("⚠️ Webhook server not running on port 5001, starting it...")
                self.start_webhook_server()
                time.sleep(2)

            def _log_refresh_error(message: str):
                now_ts = time.time()
                with self._cache_refresh_state_lock:
                    cooldown = float(self._cache_refresh_error_cooldown_s)
                    last_ts = float(self._cache_refresh_last_error_ts)
                    if (now_ts - last_ts) < cooldown:
                        return
                    self._cache_refresh_last_error_ts = now_ts
                print(message)

            def _do_refresh():
                """Background thread for cache refresh so UI never blocks"""
                try:
                    # Avoid piling up requests while a server-side refresh is already running.
                    try:
                        status_response = requests.get(
                            f'{WEBHOOK_BASE_URL}/webhook/update_all_status',
                            timeout=(1.0, 2.0),
                            headers=_webhook_headers(),
                        )
                        if status_response.status_code == 200:
                            status_payload = status_response.json() if status_response.content else {}
                            if bool(status_payload.get('in_progress', False)):
                                print("⏭️ Cache refresh already running on webhook server; skipping trigger")
                                return
                    except Exception:
                        # Status endpoint failures should not block refresh trigger.
                        pass

                    # Fail fast on response wait: server keeps working in background after trigger.
                    payload_bytes = b'{}'
                    response = requests.post(
                        f'{WEBHOOK_BASE_URL}/webhook/update_all?async=1',
                        timeout=(1.5, 2.5),
                        headers=_webhook_headers(payload_bytes, include_signature=True),
                        data=payload_bytes,
                    )
                    if response.status_code in (200, 202):
                        if response.status_code == 202:
                            print("✅ Cache refresh accepted (async job started)")
                        else:
                            print("✅ Cache refresh completed successfully")
                        if self.icon:
                            self.show_notification("Cache refresh accepted")
                    else:
                        print(f"⚠️ Cache refresh returned status {response.status_code} (non-critical)")
                except requests.exceptions.ConnectionError as e:
                    _log_refresh_error(f"⚠️ Cache refresh connection error (non-critical): {e}")
                except requests.exceptions.Timeout:
                    # Non-blocking trigger may time out under local load; treat as non-fatal noise.
                    pass
                except requests.exceptions.RequestException as e:
                    # urllib3/request adapter edge cases can surface read timeouts as RequestException.
                    if 'Read timed out' not in str(e):
                        _log_refresh_error(f"⚠️ Cache refresh request warning (non-critical): {e}")
                except Exception as e:
                    _log_refresh_error(f"⚠️ Cache refresh error (non-critical): {e}")
                finally:
                    with self._cache_refresh_state_lock:
                        self._cache_refresh_inflight = False

            # Fire the refresh in a background thread so the UI stays responsive
            refresh_thread = threading.Thread(target=_do_refresh, daemon=True)
            self.cache_refresh_thread = refresh_thread
            refresh_thread.start()
            print("🔄 Cache refresh started in background...")
            
        except Exception as e:
            with self._cache_refresh_state_lock:
                self._cache_refresh_inflight = False
            print(f"⚠️ Cache refresh error (non-critical): {e}")
            print("   Continuing without cache refresh")
    
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
            # Check if already running first
            if process_manager._is_service_running('main_dashboard'):
                # Try to bring existing window to front
                if process_manager._bring_window_to_front('main_dashboard'):
                    self.show_notification("Main Dashboard brought to front")
                else:
                    # If can't bring to front, relaunch
                    success, message = process_manager.launch_dashboard()
                    if success:
                        self.show_notification("Main Dashboard reopened")
                    else:
                        self.show_notification(f"Error: {message}")
            else:
                # Launch new instance
                success, message = process_manager.launch_dashboard()
                if success:
                    self.show_notification(message)
                else:
                    self.show_notification(f"Error: {message}")
            
            # Refresh menu to show new running service
            self.refresh_menu()
                
        except Exception as e:
            self.show_notification(f"Error opening dashboard: {e}")
    
    def open_api_dashboard(self, icon=None, item=None):
        """Open the API service dashboard using process manager"""
        try:
            # Check if already running first
            if process_manager._is_service_running('api_dashboard'):
                # Try to bring existing window to front
                if process_manager._bring_window_to_front('api_dashboard'):
                    self.show_notification("API Dashboard brought to front")
                else:
                    # If can't bring to front, relaunch
                    success, message = process_manager.launch_api_dashboard()
                    if success:
                        self.show_notification("API Dashboard reopened")
                    else:
                        self.show_notification(f"Error: {message}")
            else:
                # Launch new instance
                success, message = process_manager.launch_api_dashboard()
                if success:
                    self.show_notification(message)
                else:
                    self.show_notification(f"Error: {message}")
            
            # Refresh menu to show new running service
            self.refresh_menu()
                
        except Exception as e:
            self.show_notification(f"Error opening API dashboard: {e}")
    
    def quick_assessment(self, icon=None, item=None):
        """Start a quick assessment"""
        try:
            script_path = os.path.join(PROJECT_ROOT, 'scripts', 'v2.0', 'defi_complete_risk_assessment_clean.py')
            
            # Verify the file exists
            if not os.path.exists(script_path):
                print(f"❌ Assessment script not found: {script_path}")
                self.show_notification("Assessment script not found")
                return
            
            # Use the same Python executable as the process manager
            python_executable = process_manager.python_executable
            
            env = self._create_unified_environment()
            
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
            # Check if already running first
            if process_manager._is_service_running('credentials'):
                # Try to bring existing window to front
                if process_manager._bring_window_to_front('credentials'):
                    self.show_notification("Credential Manager brought to front")
                else:
                    # If can't bring to front, relaunch
                    success, message = process_manager.launch_credential_manager()
                    if success:
                        self.show_notification("Credential Manager reopened")
                    else:
                        self.show_notification(f"Error: {message}")
            else:
                # Launch new instance
                success, message = process_manager.launch_credential_manager()
                if success:
                    self.show_notification(message)
                else:
                    self.show_notification(f"Error: {message}")
            
            # Refresh menu to show new running service
            self.refresh_menu()
                
        except Exception as e:
            self.show_notification(f"Error opening credential manager: {e}")
    
    def manage_chains(self, icon=None, item=None):
        """Open chain management interface using process manager"""
        try:
            # Check if already running first
            if process_manager._is_service_running('chains'):
                # Try to bring existing window to front
                if process_manager._bring_window_to_front('chains'):
                    self.show_notification("Chain Manager brought to front")
                else:
                    # If can't bring to front, relaunch
                    success, message = process_manager.launch_chain_manager()
                    if success:
                        self.show_notification("Chain Manager reopened")
                    else:
                        self.show_notification(f"Error: {message}")
            else:
                # Launch new instance
                success, message = process_manager.launch_chain_manager()
                if success:
                    self.show_notification(message)
                else:
                    self.show_notification(f"Error: {message}")
            
            # Refresh menu to show new running service
            self.refresh_menu()
                
        except Exception as e:
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
            
            # Force terminate any remaining processes
            self._force_terminate_all_processes()
            
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
        
        # Create window in a thread-safe way
        try:
            # Use the process manager to launch about window as subprocess for stability
            success, message = process_manager.launch_about()
            if success:
                print(f"✅ About: {message}")
            else:
                print(f"❌ About launch failed: {message}")
                # Fallback to direct creation
                self._create_about_window()
        except Exception as e:
            print(f"❌ About window creation failed: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to direct creation
            try:
                self._create_about_window()
            except Exception as e2:
                print(f"❌ About window fallback also failed: {e2}")
                self.show_notification("About window error")
    
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
                self.show_notification("About: DeFi Risk Assessment v2.0")
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
            'Credential Manager': os.path.join(PROJECT_ROOT, 'scripts', 'v2.0', 'credential_management', 'gui_credentials.py'),
            'Chain Manager': os.path.join(PROJECT_ROOT, 'scripts', 'v2.0', 'credential_management', 'gui_chains.py'),
            'Assessment Script': os.path.join(PROJECT_ROOT, 'scripts', 'v2.0', 'defi_complete_risk_assessment_clean.py')
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
                            process_manager.terminate_service(service_name)
                        except Exception:
                            pass
            
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
                                    os.kill(pid, signal.SIGTERM)
                                    
                                    # Wait a bit and force kill if still running
                                    time.sleep(1)
                                    try:
                                        os.kill(pid, 0)
                                        os.kill(pid, signal.SIGKILL)
                                    except OSError:
                                        pass  # Process already terminated
                                        
                                except OSError:
                                    pass  # Process already dead
                                    
                        except Exception:
                            pass
            
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
                    # Access process info safely for type checker
                    info = getattr(proc, 'info', {})
                    cmdline = info.get('cmdline') if isinstance(info, dict) else None
                    if cmdline and any('defi' in arg.lower() or 'dashboard' in arg.lower() or 'credential' in arg.lower() or 'chain' in arg.lower() for arg in cmdline):
                        if proc.pid != os.getpid():  # Don't kill ourselves
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
                            except OSError:
                                pass  # Process already dead
                    except:
                        pass
        
        # Also clean up any about window processes specifically
        try:
            about_lock_file = os.path.join(self.lock_dir, 'about.lock')
            if os.path.exists(about_lock_file):
                with open(about_lock_file, 'r') as f:
                    lock_data = json.load(f)
                    pid = lock_data.get('pid')
                if pid:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except OSError:
                        pass
                os.remove(about_lock_file)
        except:
            pass
        
        # Clean up all lock files immediately
        for service_name in ['main_dashboard', 'api_dashboard', 'credentials', 'chains', 'about']:
            try:
                self._cleanup_lock(service_name)
            except Exception:
                pass
    
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
            
            # Check if pystray is available
            if not PYSTRAY_AVAILABLE:
                print("⚠️ pystray not available, running in console mode")
                print("✅ System tray functionality will be limited")
                print("✅ Right-click the magnifier icon to see menu")
            else:
                print("✅ System tray should appear in menu bar")
                print("✅ Right-click the magnifier icon to see menu")
            
            # Verify required files exist
            self.verify_required_files()
            
            # macOS compatibility setup
            if sys.platform == "darwin":
                print("✅ macOS compatibility mode enabled")
            
            print("✅ Starting system tray icon...")
            
            # Auto-launch Main Dashboard after a short delay to ensure tray icon is visible
            def _delayed_launch():
                try:
                    time.sleep(2.0)  # Give tray icon time to appear
                    if not process_manager._is_service_running('main_dashboard'):
                        success, message = process_manager.launch_dashboard()
                        if success:
                            print("✅ Main Dashboard launched after tray icon initialization")
                        else:
                            print(f"⚠️ Could not launch Main Dashboard: {message}")
                    else:
                        process_manager._bring_window_to_front('main_dashboard')
                except Exception as e:
                    print(f"⚠️ Delayed dashboard launch failed: {e}")
            
            # Start auto-launch in background thread
            threading.Thread(target=_delayed_launch, daemon=True).start()
            
            if getattr(self, 'icon', None) is not None:
                try:
                    icon_obj = cast(Any, self.icon)
                    icon_obj.run()
                except Exception:
                    print("⚠️ Failed to run system tray icon; falling back to console loop")
                    while True:
                        time.sleep(1)
            else:
                print("⚠️ Icon not initialized; running in console mode")
                while True:
                    time.sleep(1)
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
