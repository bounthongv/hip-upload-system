import os
import glob
import shutil
import mysql.connector
import time
import sys
from datetime import datetime, timedelta
import json
from cryptography.fernet import Fernet

# Configuration files
CONFIG_FILE = "config.json"
ENCRYPTED_CREDENTIALS_FILE = "encrypted_credentials.bin"

def load_config():
    """Load public configuration from JSON file"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # Create default config if file doesn't exist
        default_config = {
            "LOG_DIR": "D:\\\\Program Files (x86)\\\\HIPPremiumTime-2.0.4\\\\alog",
            "UPLOAD_TIMES": ["09:00", "12:00", "17:00", "22:00"]
        }
        save_config(default_config)
        return default_config
    except Exception as e:
        print(f"Error loading config: {e}")
        # Return default config if there's an error
        return {
            "LOG_DIR": "D:\\\\Program Files (x86)\\\\HIPPremiumTime-2.0.4\\\\alog",
            "UPLOAD_TIMES": ["09:00", "12:00", "17:00", "22:00"]
        }

def load_encrypted_credentials():
    """Load and decrypt credentials from encrypted file"""
    try:
        # Fixed encryption key - this must match the key used in encrypt_credentials.py
        ENCRYPTION_KEY = b'XZgpn7Se8pQeHY8RMyeYf6e5Twq9PdOBVo9JPsqHZA4='
        
        with open(ENCRYPTED_CREDENTIALS_FILE, 'rb') as f:
            encrypted_data = f.read()
        
        fernet = Fernet(ENCRYPTION_KEY)
        decrypted_data = fernet.decrypt(encrypted_data)
        credentials = json.loads(decrypted_data.decode())
        return credentials.get("DB_CONFIG", {})
    except FileNotFoundError:
        print(f"Encrypted credentials file {ENCRYPTED_CREDENTIALS_FILE} not found!")
        print("Please ensure encrypted_credentials.bin is in the application directory.")
        return {}
    except Exception as e:
        print(f"Error decrypting credentials: {e}")
        return {}

def save_config(config):
    """Save public configuration to JSON file"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

# Load configuration and credentials
config = load_config()
credentials = load_encrypted_credentials()

# Extract configuration values
LOG_DIR = config.get("LOG_DIR", r"D:\Program Files (x86)\HIPPremiumTime-2.0.4\alog")
PROCESSED_DIR = os.path.join(LOG_DIR, "processed")
UPLOAD_TIMES = config.get("UPLOAD_TIMES", ["09:00", "12:00", "17:00", "22:00"])

# ==========================================

if not os.path.exists(PROCESSED_DIR):
    os.makedirs(PROCESSED_DIR)

def log_msg(message):
    print(f"[{datetime.now()}] {message}")
    sys.stdout.flush()

def sync_logs():
    files = glob.glob(os.path.join(LOG_DIR, "*.txt"))
    if not files:
        return

    conn = None
    try:
        conn = mysql.connector.connect(**credentials)
        cursor = conn.cursor()

        add_log = ("INSERT IGNORE INTO device_logs "
                   "(device_sn, user_id, check_time, status, verify_type, raw_data) "
                   "VALUES (%s, %s, %s, %s, %s, %s)")

        for file_path in files:
            filename = os.path.basename(file_path)

            log_msg(f"Processing: {filename}")

            with open(file_path, 'r') as f:
                lines = f.readlines()

            count = 0
            for line in lines:
                line = line.strip()
                if not line or "---" in line or "Date Export" in line:
                    continue

                parts = line.split()
                if len(parts) >= 6:
                    user_id = parts[1]
                    date_str = f"{parts[2]} {parts[3]} {parts[4]}"
                    try:
                        dt = datetime.strptime(date_str, "%d/%m/%Y %I:%M:%S %p")
                        mysql_time = dt.strftime("%Y-%m-%d %H:%M:%S")

                        data = ('HIP_DEVICE_1', user_id, mysql_time, 0, 1, line)
                        cursor.execute(add_log, data)
                        count += 1
                    except ValueError: pass

            conn.commit()
            log_msg(f"-> Uploaded {count} records.")

            try:
                shutil.move(file_path, os.path.join(PROCESSED_DIR, filename))
            except Exception as e:
                log_msg(f"Error moving file: {e}")

    except Exception as e:
        log_msg(f"Connection Error: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()

if __name__ == "__main__":
    log_msg("=== TXT File to Cloud Sync Service Started ===")
    log_msg(f"Schedule: {UPLOAD_TIMES}")
    
    # Check if credentials are available
    if not credentials:
        log_msg("ERROR: Cannot connect to database - no credentials available!")
        log_msg("Please ensure encrypted_credentials.bin is in the application directory.")
        sys.exit(1)

    # For continuous operation with scheduled times (like original sync_to_cloud.py)
    log_msg("--- Starting scheduled sync mode ---")
    last_run_minute = None

    while True:
        now = datetime.now()
        current_time = now.strftime("%H:%M")

        # Check if current time matches schedule
        if current_time in UPLOAD_TIMES:
            if current_time != last_run_minute:
                log_msg(f"Scheduled time reached ({current_time}). Starting sync...")
                sync_logs()
                last_run_minute = current_time

        # Sleep for 30 seconds to spare CPU
        time.sleep(30)