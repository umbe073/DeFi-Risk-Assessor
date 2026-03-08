# ===============================
# ARCHIVAL: native_progress_bar.py
# This file is for historical reference only.
# Attempted to create a native macOS progress bar using osascript/System Events.
# ===============================

import subprocess
import sys
import time

class NativeProgressBar:
    def __init__(self, total_phases):
        self.total_phases = total_phases
        self.current_phase = 0
        self.progress_desc = "Initializing..."
        self._osascript_pid = None

    def update(self, phase, desc):
        self.current_phase = phase
        self.progress_desc = desc
        try:
            script = f'''tell application "System Events"
                set theProgress to make new progress bar with properties {{description: "{desc}", total steps: {self.total_phases}, completed steps: {phase}}}
            end tell'''
            subprocess.run(["osascript", "-e", script], check=True)
        except Exception as e:
            print(f"[ARCHIVAL] Native progress bar update failed: {e}")

    def close(self):
        # No reliable way to close System Events progress bar from script
        pass

# Fallback Tkinter progress bar (not used in .app)
if __name__ == "__main__":
    bar = NativeProgressBar(5)
    for i in range(1, 6):
        bar.update(i, f"Phase {i} of 5")
        time.sleep(1)
    bar.close() 