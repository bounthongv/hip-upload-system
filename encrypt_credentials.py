"""
Credential Encryption Script
For internal use only - encrypts credentials for distribution
"""
import json
import base64
from cryptography.fernet import Fernet
import os

def main():
    print("HIP System - Credential Encryption Tool")
    print("=====================================")
    
    # Fixed key that will be used in the application
    # This same key must be hardcoded in access_to_cloud.py
    FIXED_KEY = b'gAAAAABmNjQ4YzI1ZjE5ZjI0MjM4YzQ1NmI3ODlhYmMxMjM0NTY3ODlhYmMxMjM0NTY3ODlhYmMxMjM0NTY3ODlhYmMxMjM0NTY='
    
    print(f"Using fixed encryption key: {FIXED_KEY.decode()[:20]}...")
    
    # Load credentials from credentials.json
    try:
        with open('credentials.json', 'r', encoding='utf-8') as f:
            credentials = json.load(f)
    except FileNotFoundError:
        print("Error: credentials.json not found in current directory")
        print("Create a credentials.json file with your database credentials first.")
        print("Example format:")
        print('{')
        print('  "DB_CONFIG": {')
        print('    "user": "your_username",')
        print('    "password": "your_password",')
        print('    "host": "your_host",')
        print('    "database": "your_database",')
        print('    "port": 3306')
        print('  }')
        print('}')
        return
    except Exception as e:
        print(f"Error reading credentials.json: {e}")
        return
    
    # Convert credentials to JSON string
    credentials_json = json.dumps(credentials, indent=2)
    
    # Encrypt the credentials using the fixed key
    fernet = Fernet(FIXED_KEY)
    encrypted_data = fernet.encrypt(credentials_json.encode())
    
    # Save encrypted credentials
    with open('encrypted_credentials.bin', 'wb') as f:
        f.write(encrypted_data)
    
    print(f"Encryption completed!")
    print(f"- Encrypted credentials saved to: encrypted_credentials.bin")
    print(f"- Use the same fixed key in access_to_cloud.py")
    print(f"- DO NOT distribute credentials.json with the application")

if __name__ == "__main__":
    # Check if cryptography is installed
    try:
        import cryptography
    except ImportError:
        print("Error: cryptography library not found")
        print("Install it with: pip install cryptography")
        exit(1)
    
    main()