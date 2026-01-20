"""
HIP CMI F68S Device Puller - Proprietary Protocol

Implements the reverse-engineered HIP protocol (TCP 5005)
Features:
- Dynamic token extraction from handshake
- Correct packet structure (16-byte commands)
- Attendance data parsing
"""
import socket
import struct
import time
import sys
import json
from datetime import datetime
import pymysql
from cryptography.fernet import Fernet

# Config
DEVICE_IP = "192.168.100.166"
DEVICE_PORT = 5005
TIMEOUT = 10

ENCRYPTION_KEY = b'XZgpn7Se8pQeHY8RMyeYf6e5Twq9PdOBVo9JPsqHZA4='
ENCRYPTED_CREDENTIALS_FILE = "encrypted_credentials.bin"

def log_msg(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def hex_dump(data, label=""):
    if not data: return
    hex_str = ' '.join(f'{b:02x}' for b in data[:32])
    if len(data) > 32: hex_str += " ..."
    print(f"{label}: {hex_str}")

def load_encrypted_credentials():
    try:
        with open(ENCRYPTED_CREDENTIALS_FILE, 'rb') as f:
            encrypted_data = f.read()
        fernet = Fernet(ENCRYPTION_KEY)
        decrypted_data = fernet.decrypt(encrypted_data)
        credentials = json.loads(decrypted_data.decode())
        return credentials.get("DB_CONFIG", {})
    except:
        return {}

def connect_to_mysql():
    credentials = load_encrypted_credentials()
    if not credentials:
        return None
    try:
        return pymysql.connect(
            host=credentials.get('host', 'localhost'),
            user=credentials.get('user', ''),
            password=credentials.get('password', ''),
            database=credentials.get('database', ''),
            port=credentials.get('port', 3306),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
    except:
        return None

class HIPDevice:
    def __init__(self, ip, port=5005):
        self.ip = ip
        self.port = port
        self.sock = None
        
    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(TIMEOUT)
            self.sock.connect((self.ip, self.port))
            log_msg(f"Connected to {self.ip}:{self.port}")
            return True
        except Exception as e:
            log_msg(f"Connection failed: {e}")
            return False

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def send_packet(self, data):
        try:
            hex_dump(data, "Sending")
            self.sock.send(data)
            return True
        except Exception as e:
            log_msg(f"Send failed: {e}")
            return False

    def receive_packet(self, timeout=10):
        try:
            self.sock.settimeout(timeout)
            data = self.sock.recv(65535)
            hex_dump(data, "Received")
            return data
        except socket.timeout:
            log_msg("Receive timeout")
            return None
        except Exception as e:
            log_msg(f"Receive error: {e}")
            return None

    def pull_data(self):
        if not self.connect():
            return []

        records = []
        try:
            # 1. Send Handshake
            handshake = bytes.fromhex("55 aa 01 b0 00 00 00 00 00 00 00 00 00 00 00 00")
            self.send_packet(handshake)
            
            # 2. Receive Response
            resp1 = self.receive_packet(timeout=5)
            if not resp1: return []

            # 3. Send Command 2 (Get Token)
            pkt10 = bytes.fromhex("55 aa 01 b4 00 00 00 00 00 00 ff ff 00 00 18 00")
            self.send_packet(pkt10)
            
            # 4. Receive Response with Token
            resp2 = self.receive_packet(timeout=5)
            
            token = 0x03 # Default
            if resp2 and len(resp2) >= 5:
                token = resp2[4]
                log_msg(f"Extracted Token: 0x{token:02x}")
            
            time.sleep(0.1)
            
            # 5. Send Command 3 (Request Data) using Token
            # Structure: 55 aa 01 a4 00 00 00 TOKEN 20 00 00 00 00 TOKEN 19 00
            pkt12 = bytes([
                0x55, 0xaa, 0x01, 0xa4,
                0x00, 0x00, 0x00, token,
                0x20, 0x00, 0x00, 0x00,
                0x00, token,
                0x19, 0x00
            ])
            self.send_packet(pkt12)
            
            # 6. Receive BIG DATA
            data = self.receive_packet(timeout=20)
            
            if data and len(data) > 100:
                log_msg(f"Got {len(data)} bytes of data!")
                self.process_data(data)
            
        finally:
            self.disconnect()
        
        return records

    def process_data(self, data):
        # Skip header (10 bytes) if present
        if data.startswith(bytes.fromhex("aa550101")):
            data = data[10:]
            
        # Parse records (32 bytes or 40 bytes)
        # Based on packet 13 analysis, record size is likely 16 or 32
        # Let's try to extract user ID and time
        
        # Save raw dump first
        with open(f"hip_raw_{datetime.now().strftime('%H%M%S')}.bin", "wb") as f:
            f.write(data)
            
        # Parse logic would go here
        log_msg("Data saved to bin file. Parsing logic requires confirmed structure.")

def main():
    ip = sys.argv[1] if len(sys.argv) > 1 else DEVICE_IP
    device = HIPDevice(ip)
    device.pull_data()

if __name__ == "__main__":
    main()
