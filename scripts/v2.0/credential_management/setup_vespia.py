#!/usr/bin/env python3
"""
Vespia Credential Setup Script
Simple setup for secure Vespia credentials
"""

import os
import sys

def main():
    print("🔐 Vespia Secure Credential Setup")
    print("=" * 50)
    print()
    print("This script will help you set up secure Vespia credentials.")
    print("Your credentials will be encrypted and stored securely.")
    print()
    
    # Add current directory to path for secure_credentials import
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(current_dir)
    
    try:
        from secure_credentials import setup_vespia_credentials
        
        print("📋 Prerequisites:")
        print("  1. You need a Vespia account")
        print("     - Development: https://dev-my.vespia.io/sign-up")
        print("     - Production: https://my.vespia.io/sign-up")
        print()
        
        proceed = input("Ready to proceed? (y/N): ").lower().strip()
        if proceed != 'y':
            print("❌ Setup cancelled")
            return
        
        print()
        success = setup_vespia_credentials()
        
        if success:
            print()
            print("✅ Vespia credentials configured successfully!")
            print()
            print("📋 Next steps:")
            print("  1. Test your credentials: python secure_credentials.py test")
            print("  2. Run risk assessment: python defi_complete_risk_assessment.py")
            print()
            print("🔒 Your credentials are now stored securely and encrypted!")
        else:
            print()
            print("❌ Setup failed. Please try again.")
            
    except ImportError as e:
        print(f"❌ Error importing secure_credentials: {e}")
        print("Make sure secure_credentials.py is in the same directory")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main() 