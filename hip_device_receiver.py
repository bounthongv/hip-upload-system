"""
HIP CMI F68S Device Receiver - HTTP 1.0 ADMS Server

This script creates an HTTP 1.0 compatible web server that receives 
attendance data pushed from HIP CMI F68S (ZKTeco OEM) devices.

The device should be configured to push data to:
    http://<your_notebook_ip>:<port>/iclock/cdata

Device Settings (on the device or via HIP Premium Time):
    - Server Address: Your notebook's IP address
    - Server Port: 8080 (or as configured)
    - Push Data: Enable
    - Protocol: HTTP

Author: APIS Co. Ltd
Date: Jan 2026
"""

import os
import sys
import json
import time
import threading
import socket
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from socketserver import ThreadingMixIn
import pymysql
from cryptography.fernet import Fernet

# Configuration files
CONFIG_FILE = "device_receiver_config.json"
ENCRYPTED_CREDENTIALS_FILE = "encrypted_credentials.bin"
ATTENDANCE_LOG_FILE = "device_attendance.log"

# Default configuration
DEFAULT_CONFIG = {
    "SERVER_HOST": "0.0.0.0",  # Listen on all interfaces
    "SERVER_PORT": 8080,
    "DEVICE_SN": "HIP_CMI_F68S",  # Default device serial number
    "SYNC_TO_CLOUD": True,
    "SYNC_INTERVAL_SECONDS": 60,  # How often to sync pending records to cloud
    "LOG_RAW_DATA": True,
    "DEBUG_MODE": True
}

# Encryption key (same as other scripts)
ENCRYPTION_KEY = b'XZgpn7Se8pQeHY8RMyeYf6e5Twq9PdOBVo9JPsqHZA4='

# Global storage for pending records
pending_records = []
pending_lock = threading.Lock()


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
            # Merge with defaults
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


def log_attendance_to_file(record):
    """Log attendance record to local file as backup"""
    try:
        with open(ATTENDANCE_LOG_FILE, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{timestamp}|{json.dumps(record)}\n")
    except Exception as e:
        log_msg(f"Error writing to attendance log: {e}", "ERROR")


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


def sync_pending_records():
    """Sync pending records to cloud database"""
    global pending_records
    
    with pending_lock:
        if not pending_records:
            return 0
        
        records_to_sync = pending_records.copy()
        pending_records = []
    
    conn = connect_to_mysql()
    if not conn:
        # Put records back if we can't connect
        with pending_lock:
            pending_records = records_to_sync + pending_records
        log_msg("Failed to connect to MySQL, records queued for retry", "WARNING")
        return 0
    
    try:
        cursor = conn.cursor()
        
        # Check if table exists, create if not
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS device_push_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                device_sn VARCHAR(50),
                user_id VARCHAR(50),
                check_time DATETIME,
                check_type VARCHAR(10),
                verify_type VARCHAR(10),
                work_code VARCHAR(20),
                raw_data TEXT,
                received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_device_sn (device_sn),
                INDEX idx_user_id (user_id),
                INDEX idx_check_time (check_time),
                UNIQUE KEY unique_record (device_sn, user_id, check_time)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        insert_query = """
            INSERT IGNORE INTO device_push_logs 
            (device_sn, user_id, check_time, check_type, verify_type, work_code, raw_data, received_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        count = 0
        for record in records_to_sync:
            try:
                values = (
                    record.get('device_sn', ''),
                    record.get('user_id', ''),
                    record.get('check_time'),
                    record.get('check_type', ''),
                    record.get('verify_type', ''),
                    record.get('work_code', ''),
                    record.get('raw_data', ''),
                    record.get('received_at')
                )
                cursor.execute(insert_query, values)
                count += 1
            except Exception as e:
                log_msg(f"Error inserting record: {e}", "ERROR")
        
        conn.commit()
        log_msg(f"Synced {count} records to cloud database")
        return count
        
    except Exception as e:
        log_msg(f"Error syncing to MySQL: {e}", "ERROR")
        # Put records back for retry
        with pending_lock:
            pending_records = records_to_sync + pending_records
        return 0
    finally:
        if conn:
            conn.close()


class HTTP10RequestHandler(BaseHTTPRequestHandler):
    """
    HTTP 1.0 compatible request handler for ZKTeco/HIP ADMS protocol.
    
    The device sends data to various endpoints:
    - /iclock/cdata - Main data endpoint (GET for handshake, POST for data)
    - /iclock/getrequest - Device requests commands
    - /iclock/devicecmd - Device command responses
    """
    
    # Force HTTP/1.0 protocol
    protocol_version = "HTTP/1.0"
    
    def log_message(self, format, *args):
        """Override to use our logging"""
        config = load_config()
        if config.get("DEBUG_MODE", False):
            log_msg(f"{self.address_string()} - {format % args}", "DEBUG")
    
    def send_response_only(self, code, message=None):
        """Send response with HTTP/1.0"""
        if message is None:
            if code in self.responses:
                message = self.responses[code][0]
            else:
                message = ''
        self.wfile.write(f"HTTP/1.0 {code} {message}\r\n".encode('utf-8'))
    
    def do_GET(self):
        """Handle GET requests - typically device handshake/registration"""
        config = load_config()
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)
        
        if config.get("DEBUG_MODE"):
            log_msg(f"GET {self.path}", "DEBUG")
            log_msg(f"Query params: {query}", "DEBUG")
        
        if path in ['/iclock/cdata', '/iclock/cdata/']:
            self.handle_cdata_get(query)
        elif path in ['/iclock/getrequest', '/iclock/getrequest/']:
            self.handle_getrequest(query)
        else:
            # Unknown endpoint - still respond OK
            self.send_response_only(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
    
    def do_POST(self):
        """Handle POST requests - attendance data submission"""
        config = load_config()
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)
        
        # Read POST body
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8', errors='replace')
        
        if config.get("DEBUG_MODE"):
            log_msg(f"POST {self.path}", "DEBUG")
            log_msg(f"Query params: {query}", "DEBUG")
            log_msg(f"POST body: {post_data[:500]}...", "DEBUG")
        
        if path in ['/iclock/cdata', '/iclock/cdata/']:
            self.handle_cdata_post(query, post_data)
        elif path in ['/iclock/devicecmd', '/iclock/devicecmd/']:
            self.handle_devicecmd(query, post_data)
        else:
            self.send_response_only(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
    
    def handle_cdata_get(self, query):
        """
        Handle device registration/handshake.
        Device sends: GET /iclock/cdata?SN=xxxxx&options=...
        Server responds with configuration commands.
        """
        config = load_config()
        device_sn = query.get('SN', ['UNKNOWN'])[0]
        
        log_msg(f"Device handshake from SN: {device_sn}")
        
        # Response tells device what data to send and how often
        # ATTLOGStamp, OPERLOGStamp are timestamps for incremental sync
        # ErrorDelay, Delay are retry intervals
        # TransTimes is the time range to send data
        # TransInterval is how often to push (in minutes)
        response_lines = [
            f"GET OPTION FROM: {device_sn}",
            "ATTLOGStamp=0",       # Request all attendance logs from beginning
            "OPERLOGStamp=0",      # Request all operation logs from beginning  
            "ATTPHOTOStamp=0",     # Request attendance photos
            "ErrorDelay=60",       # Retry delay on error (seconds)
            "Delay=5",             # Delay between data pushes (seconds)
            "TransTimes=00:00;23:59",  # Time range to send data
            "TransInterval=1",     # Push interval (minutes)
            "TransFlag=TransData AttLog OpLog",  # What data to push
            "Realtime=1",          # Enable realtime push
            "TimeZone=7",          # Timezone offset (Thailand = UTC+7)
            "Encrypt=0",           # No encryption
        ]
        
        response_body = "\r\n".join(response_lines)
        
        self.send_response_only(200)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body.encode('utf-8'))
    
    def handle_cdata_post(self, query, post_data):
        """
        Handle attendance data POST.
        Device sends attendance records in the body.
        
        Format varies by device, common formats:
        - Tab-separated: user_id\ttimestamp\tcheck_type\tverify_type\twork_code
        - Line format: Each line is one record
        """
        config = load_config()
        device_sn = query.get('SN', [config.get('DEVICE_SN', 'UNKNOWN')])[0]
        table = query.get('table', ['ATTLOG'])[0].upper()
        
        log_msg(f"Receiving {table} data from device: {device_sn}")
        
        records_processed = 0
        received_at = datetime.now()
        
        if table == 'ATTLOG':
            # Parse attendance log
            lines = post_data.strip().split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                record = self.parse_attlog_line(line, device_sn, received_at)
                if record:
                    # Add to pending records
                    with pending_lock:
                        pending_records.append(record)
                    
                    # Log to file as backup
                    if config.get("LOG_RAW_DATA"):
                        log_attendance_to_file(record)
                    
                    records_processed += 1
                    log_msg(f"Attendance: User={record.get('user_id')} Time={record.get('check_time')}")
        
        elif table == 'OPERLOG':
            # Operation log (admin actions) - log but don't process
            log_msg(f"Received OPERLOG data: {len(post_data)} bytes")
        
        else:
            log_msg(f"Unknown table type: {table}")
        
        log_msg(f"Processed {records_processed} attendance records")
        
        # Respond with OK and stamp
        response_body = f"OK:{records_processed}"
        
        self.send_response_only(200)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body.encode('utf-8'))
    
    def parse_attlog_line(self, line, device_sn, received_at):
        """
        Parse a single attendance log line.
        
        Common formats:
        1. Tab-separated: user_id\tcheck_time\tcheck_type\tverify_type\twork_code\treserved
        2. Space-separated: Similar but with spaces
        3. HIP specific format may vary
        
        Returns dict with parsed fields or None if parsing fails.
        """
        try:
            # Try tab-separated first (most common)
            if '\t' in line:
                parts = line.split('\t')
            else:
                # Try space-separated
                parts = line.split()
            
            if len(parts) < 2:
                log_msg(f"Cannot parse line (too few parts): {line}", "WARNING")
                return None
            
            user_id = parts[0].strip()
            
            # Parse timestamp - try multiple formats
            check_time_str = parts[1].strip()
            check_time = None
            
            # Common timestamp formats from ZKTeco/HIP devices
            time_formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M:%S",
                "%d/%m/%Y %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
            ]
            
            # If time has AM/PM, adjust formats
            if len(parts) >= 3 and parts[2].upper() in ['AM', 'PM']:
                check_time_str = f"{parts[1]} {parts[2]}"
                time_formats = [
                    "%Y-%m-%d %I:%M:%S %p",
                    "%Y/%m/%d %I:%M:%S %p",
                    "%d/%m/%Y %I:%M:%S %p",
                ]
                # Adjust part indices
                check_type = parts[3] if len(parts) > 3 else ''
                verify_type = parts[4] if len(parts) > 4 else ''
                work_code = parts[5] if len(parts) > 5 else ''
            else:
                check_type = parts[2] if len(parts) > 2 else ''
                verify_type = parts[3] if len(parts) > 3 else ''
                work_code = parts[4] if len(parts) > 4 else ''
            
            for fmt in time_formats:
                try:
                    check_time = datetime.strptime(check_time_str, fmt)
                    break
                except ValueError:
                    continue
            
            if not check_time:
                log_msg(f"Cannot parse timestamp: {check_time_str}", "WARNING")
                return None
            
            return {
                'device_sn': device_sn,
                'user_id': user_id,
                'check_time': check_time.strftime("%Y-%m-%d %H:%M:%S"),
                'check_type': check_type,
                'verify_type': verify_type,
                'work_code': work_code,
                'raw_data': line,
                'received_at': received_at.strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            log_msg(f"Error parsing line '{line}': {e}", "ERROR")
            return None
    
    def handle_getrequest(self, query):
        """
        Handle device command requests.
        Device asks: What commands do you have for me?
        We respond with: No commands (or specific commands if needed)
        """
        device_sn = query.get('SN', ['UNKNOWN'])[0]
        
        if load_config().get("DEBUG_MODE"):
            log_msg(f"Command request from device: {device_sn}", "DEBUG")
        
        # Respond with OK (no pending commands)
        # To send commands, format would be: CMD_TYPE PARAM1=VAL1 PARAM2=VAL2
        response_body = "OK"
        
        self.send_response_only(200)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body.encode('utf-8'))
    
    def handle_devicecmd(self, query, post_data):
        """Handle device command responses"""
        device_sn = query.get('SN', ['UNKNOWN'])[0]
        log_msg(f"Command response from {device_sn}: {post_data[:200]}")
        
        self.send_response_only(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in separate threads"""
    allow_reuse_address = True
    daemon_threads = True


def cloud_sync_worker(interval):
    """Background worker to sync pending records to cloud"""
    log_msg(f"Cloud sync worker started (interval: {interval}s)")
    
    while True:
        try:
            time.sleep(interval)
            sync_pending_records()
        except Exception as e:
            log_msg(f"Cloud sync worker error: {e}", "ERROR")


def get_local_ip():
    """Get the local IP address that devices should connect to"""
    try:
        # Create a dummy socket to find the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def main():
    """Main entry point"""
    log_msg("=" * 60)
    log_msg("HIP CMI F68S Device Receiver - HTTP 1.0 ADMS Server")
    log_msg("=" * 60)
    
    # Load configuration
    config = load_config()
    host = config.get("SERVER_HOST", "0.0.0.0")
    port = config.get("SERVER_PORT", 8080)
    
    # Get local IP for display
    local_ip = get_local_ip()
    
    log_msg(f"Server Host: {host}")
    log_msg(f"Server Port: {port}")
    log_msg(f"Local IP Address: {local_ip}")
    log_msg("")
    log_msg("Configure your HIP CMI F68S device with:")
    log_msg(f"  Server Address: {local_ip}")
    log_msg(f"  Server Port: {port}")
    log_msg(f"  Push URL: http://{local_ip}:{port}/iclock/cdata")
    log_msg("")
    
    # Check for credentials
    credentials = load_encrypted_credentials()
    if credentials:
        log_msg("Database credentials: LOADED")
        log_msg(f"Cloud sync enabled: {config.get('SYNC_TO_CLOUD', True)}")
    else:
        log_msg("Database credentials: NOT FOUND", "WARNING")
        log_msg("Data will be saved to local file only")
        config["SYNC_TO_CLOUD"] = False
    
    log_msg("")
    
    # Start cloud sync worker thread if enabled
    if config.get("SYNC_TO_CLOUD"):
        sync_interval = config.get("SYNC_INTERVAL_SECONDS", 60)
        sync_thread = threading.Thread(
            target=cloud_sync_worker, 
            args=(sync_interval,),
            daemon=True
        )
        sync_thread.start()
    
    # Create and start HTTP server
    try:
        server = ThreadedHTTPServer((host, port), HTTP10RequestHandler)
        log_msg(f"HTTP Server started on {host}:{port}")
        log_msg("Waiting for device connections...")
        log_msg("Press Ctrl+C to stop")
        log_msg("")
        
        server.serve_forever()
        
    except KeyboardInterrupt:
        log_msg("Server stopped by user")
    except Exception as e:
        log_msg(f"Server error: {e}", "ERROR")
    finally:
        # Final sync before exit
        log_msg("Performing final sync...")
        sync_pending_records()
        log_msg("Server shutdown complete")


if __name__ == "__main__":
    main()
