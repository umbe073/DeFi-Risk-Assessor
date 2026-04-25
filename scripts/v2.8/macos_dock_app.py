#!/usr/bin/env python3
"""
macOS Dock App for DeFi Risk Assessment
This script runs inside the .app bundle and manages the unified Dock icon behavior.
It launches the system tray and provides a Dock menu for accessing sub-processes.
"""

import os
import sys
import subprocess
import threading
import time
from typing import Any, cast

try:
    # Prefer AppKit directly and ignore type checking for PyObjC symbols
    from AppKit import (  # type: ignore
        NSApplication,  # type: ignore
        NSApp,  # type: ignore
        NSObject,  # type: ignore
        NSMenu,  # type: ignore
        NSMenuItem,  # type: ignore
        NSImage,  # type: ignore
        NSApplicationActivationPolicyRegular,  # type: ignore
    )
    from objc import selector  # type: ignore
except Exception:  # Fallbacks for type checkers or non-macOS env
    NSApplication = cast(Any, None)  # type: ignore
    NSApp = cast(Any, None)  # type: ignore
    NSObject = cast(Any, object)  # type: ignore
    NSMenu = cast(Any, None)  # type: ignore
    NSMenuItem = cast(Any, None)  # type: ignore
    NSImage = cast(Any, None)  # type: ignore
    NSApplicationActivationPolicyRegular = 0  # type: ignore
    def selector(*_args: Any, **_kwargs: Any):  # type: ignore
        return None


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts", "v2.0")


def _launch_system_tray():
    """Launch the system tray with proper environment variables"""
    runner = os.path.join(SCRIPTS_DIR, "run_risk_assessment.sh")
    
    # Set up environment for unified app behavior
    env = os.environ.copy()
    env["PYTHONPATH"] = SCRIPTS_DIR
    env["PROJECT_ROOT"] = PROJECT_ROOT
    
    # Unify bundle identifiers so subprocesses inherit our app identity
    env["APP_BUNDLE"] = "true"
    env["BUNDLE_IDENTIFIER"] = "com.defi.riskassessment"
    env["CFBundleIdentifier"] = "com.defi.riskassessment"
    env["PARENT_BUNDLE_ID"] = "com.defi.riskassessment"
    env["INHERIT_BUNDLE_ID"] = "com.defi.riskassessment"
    env["FOCUS_BEHAVIOR"] = env.get("FOCUS_BEHAVIOR", "safe")
    # Provide Dock app PID and icon path for the tray
    env["DOCK_APP_PID"] = str(os.getpid())
    # Try smaller icons first for better system tray compatibility
    icon_paths = [
        os.path.join(PROJECT_ROOT, "docs", "Logos", "crypto_tiny.png"),
        os.path.join(PROJECT_ROOT, "docs", "Logos", "crypto_small.png"),
        os.path.join(PROJECT_ROOT, "docs", "Logos", "crypto.png")
    ]
    for icon_path in icon_paths:
        if os.path.exists(icon_path):
            env["TRAY_ICON_PATH"] = icon_path
            print(f"🔍 Setting TRAY_ICON_PATH to: {icon_path}")
            break
    try:
        # Debug: Print environment variables being passed
        print(f"[DockApp] TRAY_ICON_PATH in env: {env.get('TRAY_ICON_PATH', 'NOT SET')}")
        print(f"[DockApp] PROJECT_ROOT in env: {env.get('PROJECT_ROOT', 'NOT SET')}")
        # Start via shell to respect script shebang and background boot of webhook
        subprocess.Popen(["/bin/bash", runner], cwd=SCRIPTS_DIR, env=env)
    except Exception as e:
        print(f"[DockApp] Failed to launch tray: {e}")


def _service_display_map():
    return {
        "main_dashboard": "Main Dashboard",
        "api_dashboard": "API Service Dashboard",
        "credentials": "Credentials Manager",
        "chains": "Chains Manager",
        "status": "DeFi System Status",
        "settings": "Settings",
        "about": "About",
    }


class DockAppDelegate(NSObject):  # type: ignore
    """Delegate for the Dock app to handle menu and window management"""
    
    def applicationDidFinishLaunching_(self, notification):
        """Called when the app finishes launching"""
        print("🚀 Launching DeFi System Tray...")
        _launch_system_tray()
    
    def applicationShouldHandleReopen_hasVisibleWindows_(self, app, flag):
        """Handle app reactivation (clicking Dock icon)"""
        return True
    
    def applicationDockMenu_(self, sender):
        """Create the Dock menu when right-clicking the app icon"""
        try:
            menu = NSMenu.alloc().init()
            
            # Add running services to the menu
            self._add_running_services_to_menu(menu)
            
            # Add separator
            menu.addItem_(NSMenuItem.separatorItem())
            
            # Add main actions
            open_main = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Open Main Dashboard", selector(self.openMain_, signature=b"v@:@"), ""
            )
            menu.addItem_(open_main)
            
            open_api = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Open API Service Dashboard", selector(self.openAPI_, signature=b"v@:@"), ""
            )
            menu.addItem_(open_api)
            
            # Add separator
            menu.addItem_(NSMenuItem.separatorItem())
            
            # Add quit option
            quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Quit", selector(self.quitApp_, signature=b"v@:@"), "q"
            )
            menu.addItem_(quit_item)
            
            return menu
        except Exception as e:
            print(f"[DockApp] Error creating Dock menu: {e}")
            return None
    
    def _add_running_services_to_menu(self, menu):
        """Add currently running services to the Dock menu"""
        try:
            # Try to get process manager status
            process_manager = None
            try:
                sys.path.append(SCRIPTS_DIR)
                from dashboard.process_manager import ProcessManager
                process_manager = ProcessManager()
            except Exception:
                pass
            
            try:
                if process_manager is not None:
                    status = process_manager.get_service_status()
                    mapping = _service_display_map()
                    any_running = False
                    for key, display in mapping.items():
                        info = status.get(key, {}) if isinstance(status, dict) else {}
                        if info.get("running"):
                            any_running = True
                            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                                f"{display}", selector(self.bringService_, signature=b"v@:@"), ""
                            )
                            item.setRepresentedObject_(key)
                            menu.addItem_(item)
                    if not any_running:
                        placeholder = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                            "No windows", None, ""
                        )
                        placeholder.setEnabled_(False)
                        menu.addItem_(placeholder)
            except Exception:
                pass
        except Exception:
            pass
    
    def bringService_(self, sender):
        """Bring a specific service window to the front"""
        try:
            service_key = sender.representedObject()
            if service_key:
                print(f"[DockApp] Bringing {service_key} to front...")
                # Try to use process manager to bring window to front
                try:
                    sys.path.append(SCRIPTS_DIR)
                    from dashboard.process_manager import ProcessManager
                    process_manager = ProcessManager()
                    process_manager._bring_window_to_front(service_key)
                except Exception as e:
                    print(f"[DockApp] Could not bring {service_key} to front: {e}")
        except Exception as e:
            print(f"[DockApp] Error bringing service to front: {e}")
    
    def openMain_(self, sender):
        """Open the main dashboard"""
        try:
            print("[DockApp] Opening Main Dashboard...")
            sys.path.append(SCRIPTS_DIR)
            from dashboard.process_manager import ProcessManager
            process_manager = ProcessManager()
            success, message = process_manager.launch_dashboard()
            if not success:
                print(f"[DockApp] Failed to launch dashboard: {message}")
        except Exception as e:
            print(f"[DockApp] Error opening main dashboard: {e}")
    
    def openAPI_(self, sender):
        """Open the API dashboard"""
        try:
            print("[DockApp] Opening API Dashboard...")
            sys.path.append(SCRIPTS_DIR)
            from dashboard.process_manager import ProcessManager
            process_manager = ProcessManager()
            success, message = process_manager.launch_api_dashboard()
            if not success:
                print(f"[DockApp] Failed to launch API dashboard: {message}")
        except Exception as e:
            print(f"[DockApp] Error opening API dashboard: {e}")
    
    def quitApp_(self, sender):
        """Quit the application"""
        try:
            print("[DockApp] Quitting application...")
            # Terminate the system tray and all subprocesses
            try:
                sys.path.append(SCRIPTS_DIR)
                from dashboard.process_manager import ProcessManager
                process_manager = ProcessManager()
                process_manager.terminate_all_services()
            except Exception:
                pass
            # Exit the app
            NSApp.terminate_(None)
        except Exception as e:
            print(f"[DockApp] Error quitting: {e}")


def main():
    """Main entry point for the Dock app"""
    try:
        # Set up the NSApplication
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        
        # Create and set the delegate
        delegate = DockAppDelegate.alloc().init()
        app.setDelegate_(delegate)
        
        # Set the app icon
        try:
            icon_path = os.path.join(PROJECT_ROOT, "docs", "Logos", "crypto.icns")
            if os.path.exists(icon_path):
                icon = NSImage.alloc().initWithContentsOfFile_(icon_path)
                if icon:
                    app.setApplicationIconImage_(icon)
        except Exception as e:
            print(f"[DockApp] Could not set app icon: {e}")
        
        # Run the app
        print("[DockApp] Starting macOS Dock app...")
        app.run()
        
    except Exception as e:
        print(f"[DockApp] Error starting app: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
