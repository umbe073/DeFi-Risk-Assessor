#!/usr/bin/env python3
"""
Secure Credential Management System
Encrypts and stores sensitive API credentials securely
"""

import os
import base64
import getpass
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import json
import sys

class SecureCredentials:
    def __init__(self, credentials_file=".secure_credentials"):
        self.credentials_file = credentials_file
        self.master_key = None
        self.fernet = None
        
    def _generate_key_from_password(self, password, salt=None):
        """Generate encryption key from master password"""
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt
    
    def _load_or_create_master_key(self):
        """Load existing master key or create new one"""
        key_file = ".master_key"
        
        if os.path.exists(key_file):
            # Load existing master key
            with open(key_file, 'rb') as f:
                salt = f.read(16)
                key_data = f.read()
            
            # Prompt for master password
            master_password = getpass.getpass("Enter master password to unlock credentials: ")
            try:
                key, _ = self._generate_key_from_password(master_password, salt)
                self.fernet = Fernet(key)
                return True
            except Exception as e:
                print(f"❌ Invalid master password: {e}")
                return False
        else:
            # Create new master key
            print("🔐 Setting up secure credential storage...")
            master_password = getpass.getpass("Create a master password: ")
            confirm_password = getpass.getpass("Confirm master password: ")
            
            if master_password != confirm_password:
                print("❌ Passwords don't match!")
                return False
            
            if len(master_password) < 8:
                print("❌ Password must be at least 8 characters long!")
                return False
            
            # Generate key and salt
            key, salt = self._generate_key_from_password(master_password)
            self.fernet = Fernet(key)
            
            # Save salt and encrypted key
            with open(key_file, 'wb') as f:
                f.write(salt)
                f.write(key)
            
            print("✅ Master key created successfully!")
            return True
    
    def store_credentials(self, service_name, credentials):
        """Store encrypted credentials"""
        if not self._load_or_create_master_key():
            return False
        
        # Load existing credentials or create new dict
        all_credentials = self.load_all_credentials()
        all_credentials[service_name] = credentials
        
        # Encrypt and save
        encrypted_data = self.fernet.encrypt(json.dumps(all_credentials).encode())
        with open(self.credentials_file, 'wb') as f:
            f.write(encrypted_data)
        
        print(f"✅ {service_name} credentials stored securely!")
        return True
    
    def load_credentials(self, service_name):
        """Load specific service credentials"""
        if not self._load_or_create_master_key():
            return None
        
        all_credentials = self.load_all_credentials()
        return all_credentials.get(service_name)
    
    def load_all_credentials(self):
        """Load all encrypted credentials"""
        if not os.path.exists(self.credentials_file):
            return {}
        
        try:
            with open(self.credentials_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self.fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            print(f"❌ Error loading credentials: {e}")
            return {}
    
    def list_services(self):
        """List all stored services"""
        if not self._load_or_create_master_key():
            return []
        
        all_credentials = self.load_all_credentials()
        return list(all_credentials.keys())
    
    def remove_credentials(self, service_name):
        """Remove specific service credentials"""
        if not self._load_or_create_master_key():
            return False
        
        all_credentials = self.load_all_credentials()
        if service_name in all_credentials:
            del all_credentials[service_name]
            
            # Re-encrypt and save
            encrypted_data = self.fernet.encrypt(json.dumps(all_credentials).encode())
            with open(self.credentials_file, 'wb') as f:
                f.write(encrypted_data)
            
            print(f"✅ {service_name} credentials removed!")
            return True
        else:
            print(f"❌ {service_name} credentials not found!")
            return False

def setup_vespia_credentials():
    """Interactive setup for Vespia credentials"""
    secure_creds = SecureCredentials()
    
    print("🔐 Vespia Credential Setup")
    print("=" * 40)
    
    # Check if Vespia credentials already exist
    existing_creds = secure_creds.load_credentials("vespia")
    if existing_creds:
        print("📋 Existing Vespia credentials found!")
        update = input("Do you want to update them? (y/N): ").lower().strip()
        if update != 'y':
            print("✅ Keeping existing credentials")
            return True
    
    print("\n📝 Enter your Vespia credentials:")
    email = input("Email: ").strip()
    password = getpass.getpass("Password: ")
    
    if not email or not password:
        print("❌ Email and password are required!")
        return False
    
    # Store credentials
    credentials = {
        "email": email,
        "password": password
    }
    
    return secure_creds.store_credentials("vespia", credentials)

def get_vespia_credentials():
    """Get Vespia credentials securely"""
    secure_creds = SecureCredentials()
    return secure_creds.load_credentials("vespia")

def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("🔐 Secure Credential Management")
        print("=" * 40)
        print("Usage:")
        print("  python secure_credentials.py setup    - Setup Vespia credentials")
        print("  python secure_credentials.py list     - List stored services")
        print("  python secure_credentials.py remove   - Remove Vespia credentials")
        print("  python secure_credentials.py test     - Test Vespia credentials")
        return
    
    command = sys.argv[1].lower()
    secure_creds = SecureCredentials()
    
    if command == "setup":
        setup_vespia_credentials()
    
    elif command == "list":
        services = secure_creds.list_services()
        if services:
            print("📋 Stored services:")
            for service in services:
                print(f"  - {service}")
        else:
            print("📋 No services stored")
    
    elif command == "remove":
        if secure_creds.remove_credentials("vespia"):
            print("✅ Vespia credentials removed")
        else:
            print("❌ Failed to remove Vespia credentials")
    
    elif command == "test":
        creds = get_vespia_credentials()
        if creds:
            print("✅ Vespia credentials loaded successfully!")
            print(f"📧 Email: {creds['email']}")
            print("🔒 Password: [HIDDEN]")
        else:
            print("❌ No Vespia credentials found")
            print("Run 'python secure_credentials.py setup' to add them")
    
    else:
        print(f"❌ Unknown command: {command}")

if __name__ == "__main__":
    main() 