import os
import glob
import shutil
import json
import time
import sys
from datetime import datetime
import pymysql
from cryptography.fernet import Fernet

class SyncLogManager:
    """
    Manages the synchronization logic for Text Log Files (HIP/ZKTeco) to MySQL Cloud.
    Encapsulates configuration, credentials, and file processing operations.
    """
    
    # Shared fixed encryption key
    ENCRYPTION_KEY = b'XZgpn7Se8pQeHY8RMyeYf6e5Twq9PdOBVo9JPsqHZA4='

    def __init__(self, config_file="config.json", cred_file="encrypted_credentials.bin", logger_callback=None):
        self.config_file = config_file
        self.cred_file = cred_file
        self.logger_callback = logger_callback if logger_callback else self._default_logger
        self.paused = False

    def _default_logger(self, message):
        """Default logger prints to stdout"""
        print(f"[{datetime.now()}] {message}")
        sys.stdout.flush()

    def log(self, message):
        """Log a message using the configured callback"""
        self.logger_callback(message)

    def load_config(self):
        """Load public configuration from JSON file"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.log(f"Config file {self.config_file} not found. Using defaults.")
            return self._get_default_config()
        except Exception as e:
            self.log(f"Error loading config: {e}")
            return self._get_default_config()

    def _get_default_config(self):
        return {
            "LOG_DIR": "D:\\Program Files (x86)\\HIPPremiumTime-2.0.4\\alog",
            "UPLOAD_TIMES": ["09:00", "12:00", "17:00", "22:00"]
        }

    def save_config(self, config):
        """Save public configuration to JSON file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            self.log(f"Error saving config: {e}")
            return False

    def load_encrypted_credentials(self):
        """Load and decrypt credentials"""
        try:
            with open(self.cred_file, 'rb') as f:
                encrypted_data = f.read()
            
            fernet = Fernet(self.ENCRYPTION_KEY)
            decrypted_data = fernet.decrypt(encrypted_data)
            credentials = json.loads(decrypted_data.decode())
            return credentials.get("DB_CONFIG", {})
        except FileNotFoundError:
            self.log(f"Encrypted credentials file {self.cred_file} not found!")
            return {}
        except Exception as e:
            self.log(f"Error decrypting credentials: {e}")
            return {}

    def connect_to_mysql_db(self):
        """Connect to the MySQL cloud database"""
        credentials = self.load_encrypted_credentials()
        try:
            conn = pymysql.connect(
                host=credentials.get('host', 'localhost'),
                user=credentials.get('user', ''),
                password=credentials.get('password', ''),
                database=credentials.get('database', ''),
                port=credentials.get('port', 3306),
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            return conn
        except Exception as e:
            self.log(f"Error connecting to MySQL database: {e}")
            return None

    def process_logs(self):
        """Main logic to find, parse, upload, and move log files."""
        config = self.load_config()
        defaults = self._get_default_config()
        
        log_dir = config.get("LOG_DIR", defaults["LOG_DIR"])
        processed_dir = os.path.join(log_dir, "processed")

        # Ensure processed directory exists
        if not os.path.exists(processed_dir):
            try:
                os.makedirs(processed_dir)
            except Exception as e:
                self.log(f"Error creating processed directory: {e}")
                return

        files = glob.glob(os.path.join(log_dir, "*.txt"))
        if not files:
            self.log("No .txt log files found to sync.")
            return

        self.log(f"Found {len(files)} log files. Connecting to database...")

        conn = self.connect_to_mysql_db()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            add_log = ("INSERT IGNORE INTO device_logs "
                       "(device_sn, user_id, check_time, status, verify_type, raw_data) "
                       "VALUES (%s, %s, %s, %s, %s, %s)")

            for file_path in files:
                if self.paused:
                    self.log("Sync paused by user.")
                    break

                filename = os.path.basename(file_path)
                self.log(f"Processing file: {filename}")

                try:
                    with open(file_path, 'r') as f:
                        lines = f.readlines()
                except Exception as e:
                    self.log(f"Error reading file {filename}: {e}")
                    continue

                count = 0
                for line in lines:
                    line = line.strip()
                    if not line or "---" in line or "Date Export" in line:
                        continue

                    parts = line.split()
                    # Parsing logic specific to HIP Premium Time logs
                    if len(parts) >= 6:
                        user_id = parts[1]
                        # Combine date parts: e.g. "01/01/2026" "08:00:00" "AM"
                        date_str = f"{parts[2]} {parts[3]} {parts[4]}"
                        try:
                            dt = datetime.strptime(date_str, "%d/%m/%Y %I:%M:%S %p")
                            mysql_time = dt.strftime("%Y-%m-%d %H:%M:%S")

                            # Hardcoded SN as per original logic, can be improved later
                            data = ('HIP_DEVICE_1', user_id, mysql_time, 0, 1, line)
                            cursor.execute(add_log, data)
                            count += 1
                        except ValueError:
                            # Skip lines with invalid date formats
                            pass
                
                conn.commit()
                self.log(f"-> Uploaded {count} records from {filename}.")

                # Move to processed folder
                try:
                    shutil.move(file_path, os.path.join(processed_dir, filename))
                    self.log(f"-> Moved {filename} to processed folder.")
                except Exception as e:
                    self.log(f"Error moving file {filename}: {e}")

        except Exception as e:
            self.log(f"Database/Sync Error: {e}")
        finally:
            if conn:
                conn.close()

    def run_sync_cycle(self):
        """Runs one complete sync cycle."""
        self.process_logs()
