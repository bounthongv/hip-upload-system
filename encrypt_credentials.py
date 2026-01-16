"""
Credential Encryption Script
For internal use only - encrypts credentials for distribution
"""
import json
import base64
from cryptography.fernet import Fernet
import os

def generate_key():
    """Generate a key for encryption"""
    return Fernet.generate_key()

def encrypt_data(data, key):
    """Encrypt data using the provided key"""
    f = Fernet(key)
    encrypted_data = f.encrypt(data.encode())
    return encrypted_data

def main():
    print("HIP System - Credential Encryption Tool")
    print("=====================================")
    
    # Load credentials from credentials.json
    try:
        with open('credentials.json', 'r', encoding='utf-8') as f:
            credentials = json.load(f)
    except FileNotFoundError:
        print("Error: credentials.json not found in current directory")
        return
    except Exception as e:
        print(f"Error reading credentials.json: {e}")
        return
    
    # Convert credentials to JSON string
    credentials_json = json.dumps(credentials, indent=2)
    
    # Generate encryption key
    key = generate_key()
    
    # Encrypt the credentials
    encrypted_data = encrypt_data(credentials_json, key)
    
    # Save encrypted credentials
    with open('encrypted_credentials.bin', 'wb') as f:
        f.write(encrypted_data)
    
    # Save the key separately (this should be embedded in your application)
    with open('encryption_key.txt', 'w') as f:
        f.write(key.decode())
    
    print(f"Encryption completed!")
    print(f"- Encrypted credentials saved to: encrypted_credentials.bin")
    print(f"- Encryption key saved to: encryption_key.txt")
    print(f"- IMPORTANT: Keep encryption_key.txt secure and embed it in your application")
    print(f"- DO NOT distribute encryption_key.txt with the application files")

if __name__ == "__main__":
    # Check if cryptography is installed
    try:
        import cryptography
    except ImportError:
        print("Error: cryptography library not found")
        print("Install it with: pip install cryptography")
        exit(1)
    
    main()