"""
HIP CMI F68S Device Puller - TCP Direct Connection

This script connects directly to HIP CMI F68S (ZKTeco OEM) devices via TCP
using the reverse-engineered proprietary HIP protocol on port 5005.

Features:
- Proprietary Handshake (55 AA...)
- Dynamic Token Extraction
- Attendance Data Parsing
- Cloud Sync (MySQL)

Author: APIS Co. Ltd
Date: Jan 2026
"""

import os
import sys
import json
import time
import socket
import struct
from datetime import datetime
import pymysql
from cryptography.fernet import Fernet

# Configuration files
CONFIG_FILE = "device_puller_config.json"
ENCRYPTED_CREDENTIALS_FILE = "encrypted_credentials.bin"
ATTENDANCE_LOG_FILE = "device_pull_attendance.log"

# Default configuration
DEFAULT_CONFIG = {
    "DEVICES": [
        {
            "name": "HIP CMI F68S Main",
            "ip": "192.168.100.166",
            "port": 5005,
            "password": 0,
            "enabled": True
        }
    ],
    "SYNC_TO_CLOUD": True,
    "PULL_INTERVAL_MINUTES": 15,
    "CONNECTION_TIMEOUT": 10,
    "DEBUG_MODE": True
}

# Encryption key (same as other scripts)
ENCRYPTION_KEY = b'XZgpn7Se8pQeHY8RMyeYf6e5Twq9PdOBVo9JPsqHZA4='


def log_msg(message, level="INFO"):
    """Log messages with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")
    sys.stdout.flush()


def load_config():
    """Load configuration from JSON file"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
    except FileNotFoundError:
        log_msg(f"Config file not found, creating default: {CONFIG_FILE}")
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    except Exception as e:
        log_msg(f"Error loading config: {e}", "ERROR")
        return DEFAULT_CONFIG


def save_config(config):
    """Save configuration to JSON file"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        log_msg(f"Error saving config: {e}", "ERROR")
        return False


def load_encrypted_credentials():
    """Load and decrypt database credentials"""
    try:
        with open(ENCRYPTED_CREDENTIALS_FILE, 'rb') as f:
            encrypted_data = f.read()
        
        fernet = Fernet(ENCRYPTION_KEY)
        decrypted_data = fernet.decrypt(encrypted_data)
        credentials = json.loads(decrypted_data.decode())
        return credentials.get("DB_CONFIG", {})
    except FileNotFoundError:
        log_msg(f"Credentials file not found: {ENCRYPTED_CREDENTIALS_FILE}", "ERROR")
        return {}
    except Exception as e:
        log_msg(f"Error decrypting credentials: {e}", "ERROR")
        return {}


def connect_to_mysql():
    """Connect to MySQL cloud database"""
    credentials = load_encrypted_credentials()
    if not credentials:
        return None
    
    try:
        conn = pymysql.connect(
            host=credentials.get('host', 'localhost'),
            user=credentials.get('user', ''),
            password=credentials.get('password', ''),
            database=credentials.get('database', ''),
            port=credentials.get('port', 3306),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=30
        )
        return conn
    except Exception as e:
        log_msg(f"MySQL connection error: {e}", "ERROR")
        return None


def log_attendance_to_file(device_name, record):
    """Log attendance record to local file as backup"""
    try:
        with open(ATTENDANCE_LOG_FILE, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Convert record dict to JSON string
            f.write(f"{timestamp}|{device_name}|{json.dumps(record)}\n")
    except Exception as e:
        log_msg(f"Error writing to attendance log: {e}", "ERROR")


def sync_records_to_cloud(device_sn, records):
    """Sync attendance records to cloud database"""
    if not records:
        return 0
    
    conn = connect_to_mysql()
    if not conn:
        log_msg("Cannot sync to cloud - no database connection", "WARNING")
        return 0
    
    try:
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS device_pull_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                device_sn VARCHAR(50),
                user_id VARCHAR(50),
                check_time DATETIME,
                check_type VARCHAR(10),
                verify_type VARCHAR(10),
                work_code VARCHAR(20),
                raw_data TEXT,
                pulled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_device_sn (device_sn),
                INDEX idx_user_id (user_id),
                INDEX idx_check_time (check_time),
                UNIQUE KEY unique_record (device_sn, user_id, check_time)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        insert_query = """
            INSERT IGNORE INTO device_pull_logs 
            (device_sn, user_id, check_time, check_type, verify_type, work_code, raw_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        count = 0
        for record in records:
            try:
                values = (
                    device_sn,
                    record.get('user_id', ''),
                    record.get('check_time'),
                    record.get('check_type', ''),
                    record.get('verify_type', ''),
                    record.get('work_code', ''),
                    record.get('raw_data', '')
                )
                cursor.execute(insert_query, values)
                count += cursor.rowcount
            except Exception as e:
                pass
        
        conn.commit()
        return count
        
    except Exception as e:
        log_msg(f"Error syncing to MySQL: {e}", "ERROR")
        return 0
    finally:
        if conn:
            conn.close()


class HIPDevice:
    """
    HIP Proprietary Protocol Device Handler
    """
    def __init__(self, ip, port=5005, timeout=10, password=0):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.sock = None
        
    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
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
            # hex_dump(data, "Sending")
            self.sock.send(data)
            return True
        except Exception as e:
            log_msg(f"Send failed: {e}")
            return False

    def receive_packet(self, timeout=None):
        if timeout:
            self.sock.settimeout(timeout)
        try:
            data = self.sock.recv(65535)
            # hex_dump(data, "Received")
            return data
        except socket.timeout:
            # log_msg("Receive timeout")
            return None
        except Exception as e:
            log_msg(f"Receive error: {e}")
            return None

    def get_attendance_logs(self):
        """Pull attendance logs using discovered protocol"""
        if not self.connect():
            return []

        records = []
        try:
            # 1. Send Handshake (Packet 8)
            pkt8 = bytes.fromhex("55 aa 01 b0 00 00 00 00 00 00 00 00 00 00 00 00")
            self.send_packet(pkt8)
            
            resp1 = self.receive_packet(timeout=5)
            if not resp1:
                log_msg("No handshake response")
                return []

            # 2. Send Command 2 (Setup)
            pkt10 = bytes.fromhex("55 aa 01 b4 00 00 00 00 00 00 ff ff 00 00 18 00")
            self.send_packet(pkt10)
            
            resp2 = self.receive_packet(timeout=5)
            
            token = 0x03 # Default token
            if resp2 and len(resp2) >= 5:
                token = resp2[4]
                # log_msg(f"Extracted Token: 0x{token:02x}")
            
            time.sleep(0.1)
            
            # 3. Request Logs (Packet 12)
            pkt12 = bytes([
                0x55, 0xaa, 0x01, 0xa4,
                0x00, 0x00, 0x00, token,
                0x20, 0x00, 0x00, 0x00,
                0x00, token,
                0x19, 0x00
            ])
            self.send_packet(pkt12)
            
            # 4. Receive Data
            data = self.receive_packet(timeout=20)
            
            if data and len(data) > 100:
                log_msg(f"Received {len(data)} bytes of log data")
                records = self.parse_attendance_data(data)
                log_msg(f"Parsed {len(records)} attendance records")
            
        finally:
            self.disconnect()
        
        return records

    def parse_attendance_data(self, data):
        """Parse raw data into structured records using 20-byte layout"""
        records = []
        
        # Header is usually 10 bytes + 2 bytes padding/wrapper?
        # Based on analysis: payload starts at offset 12
        offset = 12
        if len(data) < offset + 20:
            return []
            
        payload = data[offset:]
        record_size = 20
        num_records = len(payload) // record_size
        
        log_msg(f"Parsing {num_records} records from {len(data)} bytes")
        
        # TIME CORRECTION
        # The device clock appears to be reset/stuck in ~2012.
        # We calculated a constant offset based on ground truth data from Jan 2026.
        # Real Time (2026) - Device Time (2012) = 442,238,549 seconds
        # This corrects for the ~14 year shift and timezone alignment.
        TIME_OFFSET = 442238549
        
        for i in range(num_records):
            chunk = payload[i*record_size : (i+1)*record_size]
            
            try:
                # Layout:
                # 0-4: User ID (LE)
                # 4-7: ?
                # 7-11: Timestamp (LE)
                # 11-15: ?
                # 15-19: Work Code (LE)
                # 19: Verify Mode (Byte)
                
                uid = struct.unpack("<I", chunk[0:4])[0]
                ts_val = struct.unpack("<I", chunk[7:11])[0]
                work_code = struct.unpack("<I", chunk[15:19])[0]
                verify_mode = chunk[19] # Byte
                
                # Checksum/Sanity check: UID should be reasonable
                if uid == 0 or uid > 100000000:
                    continue
                    
                # Apply Time Correction
                corrected_ts = ts_val + TIME_OFFSET
                    
                # Timestamp conversion
                try:
                    # Basic Unix Timestamp
                    check_time = datetime.fromtimestamp(corrected_ts).strftime("%Y-%m-%d %H:%M:%S")
                except:
                    # Fallback if correction fails (e.g. invalid TS)
                    check_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Verify Mode Mapping
                # 0x40 (64) -> 1 (Finger/Pwd)
                # 0x10 (16) -> 1 (Card/Face)
                v_mode_str = str(verify_mode)
                if verify_mode == 0x40: v_mode_str = "1"
                elif verify_mode == 0x10: v_mode_str = "1" 
                
                records.append({
                    'user_id': str(uid),
                    'check_time': check_time,
                    'check_type': 'I', # Default to Check-In
                    'verify_type': v_mode_str,
                    'work_code': str(work_code),
                    'raw_data': chunk.hex()
                })
                
            except Exception as e:
                log_msg(f"Error parsing record {i}: {e}")
                
        return records


def pull_from_device(device_config):
    """Pull attendance data from a single device"""
    name = device_config.get('name', 'Unknown')
    ip = device_config.get('ip', '')
    port = device_config.get('port', 5005)
    
    log_msg(f"Pulling from device: {name} ({ip}:{port})")
    
    try:
        device = HIPDevice(ip, port)
        records = device.get_attendance_logs()
        
        if records:
            # Sync to cloud
            config = load_config()
            if config.get('SYNC_TO_CLOUD'):
                # For raw dumps, we might need a special table or just log it
                # But let's try to sync what we have
                synced = sync_records_to_cloud(f"{name}_{ip}", records)
                log_msg(f"Synced {synced} records/blobs to cloud")
            
            return len(records)
        else:
            log_msg(f"No new records from {name}")
            return 0
            
    except Exception as e:
        log_msg(f"Error pulling from {name}: {e}", "ERROR")
        return 0


def pull_all_devices():
    """Pull attendance data from all configured devices"""
    config = load_config()
    devices = config.get('DEVICES', [])
    
    total_records = 0
    for device_config in devices:
        if not device_config.get('enabled', True):
            continue
        records = pull_from_device(device_config)
        total_records += records
    
    return total_records


def run_scheduled():
    """Run in scheduled mode"""
    config = load_config()
    interval = config.get('PULL_INTERVAL_MINUTES', 15)
    
    log_msg(f"Starting scheduled pull (every {interval} min)")
    while True:
        try:
            pull_all_devices()
            time.sleep(interval * 60)
        except KeyboardInterrupt:
            break
        except Exception:
            time.sleep(60)


def run_once():
    """Run a single pull"""
    pull_all_devices()


def test_connection(ip, port=5005):
    """Test connection"""
    device = HIPDevice(ip, port)
    if device.connect():
        log_msg("Connection successful!")
        device.disconnect()
        return True
    else:
        log_msg("Connection failed!")
        return False


def main():
    log_msg("=" * 60)
    log_msg("HIP CMI F68S Device Puller (Proprietary Protocol)")
    log_msg("=" * 60)
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == 'test':
            ip = sys.argv[2] if len(sys.argv) > 2 else "192.168.100.166"
            test_connection(ip)
        elif cmd == 'once':
            run_once()
        elif cmd == 'scheduled':
            run_scheduled()
        else:
            print("Usage: python hip_device_puller.py [test|once|scheduled]")
    else:
        # Default behavior
        print("1. Test Connection")
        print("2. Pull Once")
        print("3. Scheduled Mode")
        try:
            choice = input("Choice: ")
            if choice == '1': test_connection(input("IP: "))
            elif choice == '2': run_once()
            elif choice == '3': run_scheduled()
        except: pass

if __name__ == "__main__":
    main()
