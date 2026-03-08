#!/usr/bin/env python3
"""
Credential Management Tool
Easy way to manage Vespia credentials
"""

import os
import sys
import getpass
from pathlib import Path

def get_venv_python():
    """Get the Python executable from the virtual environment"""
    current_dir = Path(__file__).parent
    venv_root = current_dir.parent.parent.parent
    venv_python = venv_root / "bin" / "python3"
    
    if venv_python.exists():
        return str(venv_python)
    else:
        raise FileNotFoundError(f"Virtual environment Python not found at {venv_python}")

def main():
    print("🔐 Vespia Credential Management")
    print("=" * 40)
    print()
    
    # Get the virtual environment Python
    try:
        venv_python = get_venv_python()
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return
    
    # Add current directory to path for secure_credentials import
    current_dir = Path(__file__).parent
    sys.path.append(str(current_dir))
    
    try:
        from secure_credentials import SecureCredentials, get_vespia_credentials
        
        secure_creds = SecureCredentials()
        
        print("📋 Available actions:")
        print("1. View current credentials")
        print("2. Update email")
        print("3. Update password")
        print("4. Update both email and password")
        print("5. Remove credentials")
        print("6. Test credentials")
        print("7. Exit")
        print()
        
        while True:
            try:
                choice = input("Enter your choice (1-7): ").strip()
                
                if choice == "1":
                    print("\n📧 Current Vespia credentials:")
                    creds = get_vespia_credentials()
                    if creds:
                        print(f"   Email: {creds.get('email', 'Not set')}")
                        print("   Password: [HIDDEN]")
                    else:
                        print("   No credentials configured")
                    print()
                    
                elif choice == "2":
                    print("\n📧 Update Vespia email:")
                    new_email = input("Enter new email: ").strip()
                    if new_email:
                        creds = get_vespia_credentials() or {}
                        creds['email'] = new_email
                        if secure_creds.store_credentials("vespia", creds):
                            print("✅ Email updated successfully!")
                        else:
                            print("❌ Failed to update email")
                    else:
                        print("❌ Email cannot be empty")
                    print()
                    
                elif choice == "3":
                    print("\n🔒 Update Vespia password:")
                    new_password = getpass.getpass("Enter new password: ")
                    if new_password:
                        creds = get_vespia_credentials() or {}
                        creds['password'] = new_password
                        if secure_creds.store_credentials("vespia", creds):
                            print("✅ Password updated successfully!")
                        else:
                            print("❌ Failed to update password")
                    else:
                        print("❌ Password cannot be empty")
                    print()
                    
                elif choice == "4":
                    print("\n📧🔒 Update both email and password:")
                    new_email = input("Enter new email: ").strip()
                    new_password = getpass.getpass("Enter new password: ")
                    
                    if new_email and new_password:
                        creds = {
                            'email': new_email,
                            'password': new_password
                        }
                        if secure_creds.store_credentials("vespia", creds):
                            print("✅ Credentials updated successfully!")
                        else:
                            print("❌ Failed to update credentials")
                    else:
                        print("❌ Both email and password are required")
                    print()
                    
                elif choice == "5":
                    print("\n🗑️  Remove Vespia credentials:")
                    confirm = input("Are you sure? This will delete your credentials. (y/N): ").strip().lower()
                    if confirm == 'y':
                        if secure_creds.remove_credentials("vespia"):
                            print("✅ Credentials removed successfully!")
                        else:
                            print("❌ Failed to remove credentials")
                    else:
                        print("✅ Operation cancelled")
                    print()
                    
                elif choice == "6":
                    print("\n🧪 Testing Vespia credentials:")
                    creds = get_vespia_credentials()
                    if creds:
                        print(f"   Email: {creds.get('email', 'Not set')}")
                        print("   Password: [HIDDEN]")
                        print("   Status: ✅ Credentials found")
                    else:
                        print("   Status: ❌ No credentials found")
                    print()
                    
                elif choice == "7":
                    print("\n👋 Goodbye!")
                    break
                    
                else:
                    print("❌ Invalid choice. Please enter 1-7.")
                    print()
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                print()
                
    except ImportError as e:
        print(f"❌ Error importing secure_credentials: {e}")
        print("Make sure secure_credentials.py is in the same directory")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main() 