#!/usr/bin/env python3
"""
Cleanup script for Token Editor lock file
=========================================

This script manually removes the token editor lock file if it gets stuck.
Use this if you get the "Token Editor is already running" error but no window is visible.
"""

import tempfile
from pathlib import Path

def cleanup_token_editor_lock():
    """Remove the token editor lock file"""
    try:
        temp_dir = Path(tempfile.gettempdir())
        lock_file = temp_dir / "token_editor.lock"
        
        if lock_file.exists():
            print(f"Found lock file: {lock_file}")
            
            # Try to read the PID
            try:
                with open(lock_file, 'r') as f:
                    pid = f.read().strip()
                print(f"Lock file contains PID: {pid}")
            except Exception as e:
                print(f"Could not read PID from lock file: {e}")
            
            # Remove the lock file
            lock_file.unlink()
            print("✅ Token editor lock file removed successfully!")
            print("You can now open the Token Editor again.")
            return True
        else:
            print("ℹ️  No token editor lock file found.")
            print("The Token Editor should be able to start normally.")
            return False
            
    except Exception as e:
        print(f"❌ Error removing token editor lock file: {e}")
        return False

if __name__ == "__main__":
    print("🧹 Token Editor Lock File Cleanup")
    print("=" * 40)
    cleanup_token_editor_lock()

