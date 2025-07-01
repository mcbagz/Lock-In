"""
AI Security Manager for LockIn
Handles secure storage and retrieval of API keys using Windows DPAPI
"""

import os
import base64
from pathlib import Path
from typing import Optional
import platform

# Windows-specific imports
if platform.system() == "Windows":
    try:
        import win32crypt
        WINDOWS_DPAPI_AVAILABLE = True
    except ImportError:
        WINDOWS_DPAPI_AVAILABLE = False
else:
    WINDOWS_DPAPI_AVAILABLE = False

# Fallback encryption for non-Windows or if DPAPI unavailable
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import secrets


class AISecurityManager:
    def __init__(self, config_dir: str = "config"):
        """Initialize the security manager"""
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        self.api_key_file = self.config_dir / "api_keys.enc"
        self.salt_file = self.config_dir / ".salt"
        
    def _get_machine_key(self) -> bytes:
        """Generate or retrieve a machine-specific key for encryption"""
        if not self.salt_file.exists():
            # Generate a new salt
            salt = secrets.token_bytes(32)
            with open(self.salt_file, 'wb') as f:
                f.write(salt)
        else:
            with open(self.salt_file, 'rb') as f:
                salt = f.read()
        
        # Use machine-specific information to derive key
        machine_info = f"{platform.machine()}-{platform.processor()}-{os.environ.get('COMPUTERNAME', 'unknown')}"
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(machine_info.encode()))
        return key
        
    def _encrypt_with_dpapi(self, data: str) -> bytes:
        """Encrypt data using Windows DPAPI"""
        if not WINDOWS_DPAPI_AVAILABLE:
            raise RuntimeError("Windows DPAPI not available")
        
        try:
            encrypted_data = win32crypt.CryptProtectData(
                data.encode('utf-8'),  # Data to encrypt
                None,  # Optional description
                None,  # Optional entropy
                None,  # Reserved
                None,  # Prompt struct
                0      # Flags
            )
            return encrypted_data
        except Exception as e:
            raise RuntimeError(f"Failed to encrypt with DPAPI: {e}")
    
    def _decrypt_with_dpapi(self, encrypted_data: bytes) -> str:
        """Decrypt data using Windows DPAPI"""
        if not WINDOWS_DPAPI_AVAILABLE:
            raise RuntimeError("Windows DPAPI not available")
        
        try:
            decrypted_data, description = win32crypt.CryptUnprotectData(
                encrypted_data,
                None,  # Optional entropy
                None,  # Reserved
                None,  # Prompt struct
                0      # Flags
            )
            
            # Check where the actual data is - sometimes it's in description
            if decrypted_data and (isinstance(decrypted_data, (str, bytes))):
                # Data is in the normal place
                if isinstance(decrypted_data, bytes):
                    result = decrypted_data.decode('utf-8')
                else:
                    result = decrypted_data
            elif description and isinstance(description, bytes):
                # Data is in the description field (this seems to be what's happening)
                result = description.decode('utf-8')
            elif description:
                result = str(description)
            else:
                result = ""
            
            return result
        except Exception as e:
            raise RuntimeError(f"Failed to decrypt with DPAPI: {e}")
    
    def _encrypt_with_fernet(self, data: str) -> bytes:
        """Encrypt data using Fernet (fallback encryption)"""
        key = self._get_machine_key()
        fernet = Fernet(key)
        return fernet.encrypt(data.encode('utf-8'))
    
    def _decrypt_with_fernet(self, encrypted_data: bytes) -> str:
        """Decrypt data using Fernet (fallback encryption)"""
        key = self._get_machine_key()
        fernet = Fernet(key)
        return fernet.decrypt(encrypted_data).decode('utf-8')
    
    def store_api_key(self, service: str, api_key: str) -> bool:
        """Store an API key securely"""
        try:
            # Load existing keys or create new dict
            keys = self._load_all_keys()
            keys[service] = api_key
            
            # Serialize keys using proper JSON
            import json
            keys_json = json.dumps(keys)
            
            # Encrypt using preferred method
            if WINDOWS_DPAPI_AVAILABLE and platform.system() == "Windows":
                encrypted_data = self._encrypt_with_dpapi(keys_json)
                # Add a marker to indicate DPAPI encryption
                encrypted_data = b"DPAPI:" + encrypted_data
            else:
                encrypted_data = self._encrypt_with_fernet(keys_json)
                # Add a marker to indicate Fernet encryption
                encrypted_data = b"FERNET:" + encrypted_data
            
            # Save to file
            with open(self.api_key_file, 'wb') as f:
                f.write(encrypted_data)
            
            return True
            
        except Exception as e:
            print(f"Error storing API key: {e}")
            return False
    
    def get_api_key(self, service: str) -> Optional[str]:
        """Retrieve an API key securely"""
        try:
            keys = self._load_all_keys()
            return keys.get(service)
        except Exception as e:
            print(f"Error retrieving API key: {e}")
            return None
    
    def _load_all_keys(self) -> dict:
        """Load all stored API keys"""
        if not self.api_key_file.exists():
            return {}
        
        try:
            with open(self.api_key_file, 'rb') as f:
                encrypted_data = f.read()
            
            # Check if file is empty
            if not encrypted_data:
                return {}
            
            # Determine encryption method and decrypt
            if encrypted_data.startswith(b"DPAPI:"):
                encrypted_data = encrypted_data[6:]  # Remove marker
                keys_json = self._decrypt_with_dpapi(encrypted_data)
            elif encrypted_data.startswith(b"FERNET:"):
                encrypted_data = encrypted_data[7:]  # Remove marker
                keys_json = self._decrypt_with_fernet(encrypted_data)
            else:
                # Legacy format, try DPAPI first, then Fernet
                try:
                    if WINDOWS_DPAPI_AVAILABLE:
                        keys_json = self._decrypt_with_dpapi(encrypted_data)
                    else:
                        keys_json = self._decrypt_with_fernet(encrypted_data)
                except:
                    keys_json = self._decrypt_with_fernet(encrypted_data)
            
            # Check if decrypted content is empty
            if not keys_json or keys_json.strip() == "":
                return {}
            
            # Parse the JSON string properly
            import json
            keys = json.loads(keys_json)
            return keys if isinstance(keys, dict) else {}
            
        except Exception as e:
            print(f"Error loading API keys: {e}")
            # If there's an error, remove the corrupted file
            try:
                self.api_key_file.unlink(missing_ok=True)
            except:
                pass
            return {}
    
    def delete_api_key(self, service: str) -> bool:
        """Delete a stored API key"""
        try:
            keys = self._load_all_keys()
            if service in keys:
                del keys[service]
                
                if keys:
                    # Save remaining keys
                    import json
                    keys_json = json.dumps(keys)
                    if WINDOWS_DPAPI_AVAILABLE and platform.system() == "Windows":
                        encrypted_data = b"DPAPI:" + self._encrypt_with_dpapi(keys_json)
                    else:
                        encrypted_data = b"FERNET:" + self._encrypt_with_fernet(keys_json)
                    
                    with open(self.api_key_file, 'wb') as f:
                        f.write(encrypted_data)
                else:
                    # No keys left, delete file
                    self.api_key_file.unlink(missing_ok=True)
                
                return True
            return False
            
        except Exception as e:
            print(f"Error deleting API key: {e}")
            return False
    
    def has_api_key(self, service: str) -> bool:
        """Check if an API key is stored for a service"""
        keys = self._load_all_keys()
        return service in keys and keys[service] is not None and keys[service].strip() != ""
    
    def list_stored_services(self) -> list:
        """List all services with stored API keys"""
        keys = self._load_all_keys()
        return list(keys.keys())
    
    def validate_api_key_format(self, service: str, api_key: str) -> bool:
        """Validate API key format for known services"""
        if service.lower() == "openai":
            # OpenAI keys can start with 'sk-' (legacy) or 'sk-proj-' (project-based)
            # They are typically between 40-200 characters (project keys can be longer)
            valid_prefixes = ["sk-", "sk-proj-"]
            has_valid_prefix = any(api_key.startswith(prefix) for prefix in valid_prefixes)
            
            return (has_valid_prefix and 
                   len(api_key) >= 40 and 
                   len(api_key) <= 200)  # Increased upper limit for project keys
        
        # For unknown services, just check it's not empty
        return api_key.strip() != ""
    
    def clear_all_keys(self) -> bool:
        """Clear all stored API keys (for testing or reset)"""
        try:
            self.api_key_file.unlink(missing_ok=True)
            self.salt_file.unlink(missing_ok=True)
            return True
        except Exception as e:
            print(f"Error clearing all keys: {e}")
            return False


# Convenience functions
def get_openai_api_key() -> Optional[str]:
    """Get the stored OpenAI API key"""
    security_manager = AISecurityManager()
    return security_manager.get_api_key("openai")


def store_openai_api_key(api_key: str) -> bool:
    """Store the OpenAI API key securely"""
    security_manager = AISecurityManager()
    
    if security_manager.validate_api_key_format("openai", api_key):
        return security_manager.store_api_key("openai", api_key)
    return False


def has_openai_api_key() -> bool:
    """Check if OpenAI API key is stored"""
    security_manager = AISecurityManager()
    return security_manager.has_api_key("openai") 