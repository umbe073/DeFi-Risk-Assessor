#!/usr/bin/env python3
"""
Secure Credentials Manager
==========================

Encrypts/decrypts API credentials for the risk assessor.
Stores:
- data/creds.meta -> JSON: {"salt": base64}
- data/creds.enc  -> Fernet ciphertext of JSON map {KEY: VALUE}

Usage:
  secure_credentials.py setup                # initialize files (prompts master password)
  secure_credentials.py test                 # verify decryption
  secure_credentials.py list                 # list keys (names only)
  secure_credentials.py get KEY              # print value for KEY
  secure_credentials.py set KEY VALUE        # set/update a key
  secure_credentials.py remove KEY           # delete a key
  secure_credentials.py import_env PATH      # import from .env-like file
  secure_credentials.py export_env PATH      # export to .env-like file
  secure_credentials.py rotate               # change master password

Reads MASTER_PASSWORD from env; if not present, prompts securely.
"""

import os
import sys
import json
import base64
import getpass
from typing import Dict

try:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.fernet import Fernet, InvalidToken
except Exception as e:
    print("❌ cryptography not available. Install with: pip install cryptography")
    sys.exit(1)


def project_paths():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
    data_dir = os.path.join(project_root, 'data')
    os.makedirs(data_dir, exist_ok=True)
    return {
        'project_root': project_root,
        'data_dir': data_dir,
        'enc_path': os.path.join(data_dir, 'creds.enc'),
        'meta_path': os.path.join(data_dir, 'creds.meta')
    }


def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def get_master_password(prompt: str = "Enter master password: ") -> str:
    return os.getenv('MASTER_PASSWORD') or getpass.getpass(prompt)


def read_store(enc_path: str, meta_path: str, master: str) -> Dict[str, str]:
    if not (os.path.exists(enc_path) and os.path.exists(meta_path)):
        return {}
    with open(meta_path, 'r') as f:
        meta = json.load(f)
    salt = base64.b64decode(meta.get('salt', ''))
    key = derive_key(master, salt)
    with open(enc_path, 'rb') as f:
        token = f.read()
    try:
        data = Fernet(key).decrypt(token)
        obj = json.loads(data.decode())
        if not isinstance(obj, dict):
            raise ValueError('Invalid credentials payload')
        return {str(k): str(v) for k, v in obj.items()}
    except InvalidToken:
        # This is specifically a wrong password error
        raise ValueError("Incorrect master password. Please check your password and try again.")
    except Exception as e:
        # Re-raise other exceptions as-is
        raise e


def write_store(enc_path: str, meta_path: str, master: str, kv: Dict[str, str], salt: bytes = None) -> None:
    if salt is None:
        salt = os.urandom(16)
    key = derive_key(master, salt)
    token = Fernet(key).encrypt(json.dumps(kv, indent=2).encode())
    with open(enc_path, 'wb') as f:
        f.write(token)
    with open(meta_path, 'w') as f:
        json.dump({'salt': base64.b64encode(salt).decode()}, f, indent=2)


def cmd_setup(paths):
    print("🔐 Setting up encrypted credential store...")
    master = get_master_password()
    confirm = os.getenv('MASTER_PASSWORD') or getpass.getpass('Confirm master password: ')
    if master != confirm:
        print('❌ Passwords do not match')
        return 1
    write_store(paths['enc_path'], paths['meta_path'], master, {})
    print('✅ Encrypted store initialized')
    return 0


def cmd_test(paths):
    try:
        master = get_master_password()
        _ = read_store(paths['enc_path'], paths['meta_path'], master)
        print('✅ Encrypted store is readable')
        return 0
    except Exception as e:
        print(f'❌ Test failed: {e}')
        return 1


def cmd_list(paths):
    try:
        master = get_master_password()
        kv = read_store(paths['enc_path'], paths['meta_path'], master)
        if not kv:
            print('(empty)')
        else:
            for k in sorted(kv.keys()):
                print(k)
        return 0
    except Exception as e:
        print(f'❌ {e}')
        return 1


def cmd_get(paths, key):
    try:
        master = get_master_password()
        kv = read_store(paths['enc_path'], paths['meta_path'], master)
        print(kv.get(key, ''))
        return 0
    except Exception as e:
        print(f'❌ {e}')
        return 1


def cmd_set(paths, key, value):
    try:
        master = get_master_password()
        kv = read_store(paths['enc_path'], paths['meta_path'], master)
        kv[str(key)] = str(value)
        # do not print sensitive
        with open(paths['meta_path'], 'r') as f:
            meta = json.load(f)
        salt = base64.b64decode(meta.get('salt', ''))
        write_store(paths['enc_path'], paths['meta_path'], master, kv, salt)
        print('✅ Set')
        return 0
    except Exception as e:
        print(f'❌ {e}')
        return 1


def cmd_remove(paths, key):
    try:
        master = get_master_password()
        kv = read_store(paths['enc_path'], paths['meta_path'], master)
        if key in kv:
            kv.pop(key)
            with open(paths['meta_path'], 'r') as f:
                meta = json.load(f)
            salt = base64.b64decode(meta.get('salt', ''))
            write_store(paths['enc_path'], paths['meta_path'], master, kv, salt)
            print('✅ Removed')
        else:
            print('ℹ️  Not found')
        return 0
    except Exception as e:
        print(f'❌ {e}')
        return 1


def parse_env_file(path: str) -> Dict[str, str]:
    kv = {}
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                kv[k.strip()] = v.strip().strip('"').strip("'")
    return kv


def cmd_import_env(paths, env_path):
    try:
        master = get_master_password()
        current = read_store(paths['enc_path'], paths['meta_path'], master)
        add = parse_env_file(env_path)
        current.update(add)
        with open(paths['meta_path'], 'r') as f:
            meta = json.load(f)
        salt = base64.b64decode(meta.get('salt', ''))
        write_store(paths['enc_path'], paths['meta_path'], master, current, salt)
        print(f'✅ Imported {len(add)} keys')
        return 0
    except Exception as e:
        print(f'❌ {e}')
        return 1


def cmd_export_env(paths, env_path):
    try:
        master = get_master_password()
        kv = read_store(paths['enc_path'], paths['meta_path'], master)
        with open(env_path, 'w') as f:
            for k, v in kv.items():
                f.write(f"{k}={v}\n")
        print(f'✅ Exported {len(kv)} keys to {env_path}')
        return 0
    except Exception as e:
        print(f'❌ {e}')
        return 1


def cmd_rotate(paths):
    try:
        old_master = get_master_password('Enter current master password: ')
        kv = read_store(paths['enc_path'], paths['meta_path'], old_master)
        new_master = getpass.getpass('Enter NEW master password: ')
        confirm = getpass.getpass('Confirm NEW master password: ')
        if new_master != confirm:
            print('❌ Passwords do not match')
            return 1
        write_store(paths['enc_path'], paths['meta_path'], new_master, kv)
        print('✅ Master password rotated')
        return 0
    except Exception as e:
        print(f'❌ {e}')
        return 1


def main(argv):
    p = project_paths()
    if len(argv) < 2:
        print(__doc__)
        return 0
    cmd = argv[1]
    if cmd == 'setup':
        return cmd_setup(p)
    if cmd == 'test':
        return cmd_test(p)
    if cmd == 'list':
        return cmd_list(p)
    if cmd == 'get' and len(argv) >= 3:
        return cmd_get(p, argv[2])
    if cmd == 'set' and len(argv) >= 4:
        return cmd_set(p, argv[2], argv[3])
    if cmd == 'remove' and len(argv) >= 3:
        return cmd_remove(p, argv[2])
    if cmd == 'import_env' and len(argv) >= 3:
        return cmd_import_env(p, argv[2])
    if cmd == 'export_env' and len(argv) >= 3:
        return cmd_export_env(p, argv[2])
    if cmd == 'rotate':
        return cmd_rotate(p)
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))

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