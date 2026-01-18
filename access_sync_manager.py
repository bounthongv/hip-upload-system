import os
import json
import time
import sys
from datetime import datetime
import pyodbc
import pymysql
from cryptography.fernet import Fernet

class AccessSyncManager:
    """
    Manages the synchronization logic between MS Access and MySQL Cloud.
    encapsulates configuration, credentials, and sync operations.
    """
    
    # Fixed encryption key as requested
    ENCRYPTION_KEY = b'XZgpn7Se8pQeHY8RMyeYf6e5Twq9PdOBVo9JPsqHZA4='

    def __init__(self, config_file="config.json", cred_file="encrypted_credentials.bin", logger_callback=None):
        self.config_file = config_file
        self.cred_file = cred_file
        self.logger_callback = logger_callback if logger_callback else self._default_logger
        self.paused = False
        self.running = False

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
            "ACCESS_DB_PATH": "D:\\Program Files (x86)\\HIPPremiumTime-2.0.4\\db\\Pm2014.mdb",
            "ACCESS_PASSWORD": "hippmforyou",
            "UPLOAD_TIMES": ["09:00", "12:00", "17:00", "22:00"],
            "LAST_SYNC_FILE": "last_sync_access.txt",
            "BATCH_SIZE": 100
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

    def get_last_sync_position(self):
        """Get the last sync position (timestamp and SN) from file"""
        config = self.load_config()
        last_sync_file = config.get("LAST_SYNC_FILE", "last_sync_access.txt")
        try:
            with open(last_sync_file, 'r') as f:
                content = f.read().strip()
                if '|' in content:
                    timestamp_part, sn_part = content.rsplit('|', 1)
                    return timestamp_part, sn_part
                else:
                    return content, None
        except FileNotFoundError:
            return None, None

    def set_last_sync_position(self, timestamp, sn):
        """Save the last sync position (timestamp and SN) to file"""
        config = self.load_config()
        last_sync_file = config.get("LAST_SYNC_FILE", "last_sync_access.txt")
        try:
            with open(last_sync_file, 'w') as f:
                f.write(f"{timestamp}|{sn}")
        except Exception as e:
            self.log(f"Error saving sync position: {e}")

    def connect_to_access_db(self):
        """Connect to the MS Access database"""
        config = self.load_config()
        db_path = config.get("ACCESS_DB_PATH", self._get_default_config()["ACCESS_DB_PATH"])
        password = config.get("ACCESS_PASSWORD", "hippmforyou")

        try:
            conn_str = (
                r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
                f"DBQ={db_path};"
                f"PWD={password}"
            )
            conn = pyodbc.connect(conn_str)
            return conn
        except Exception as e:
            self.log(f"Error connecting to Access database: {e}")
            return None

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
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=60,
                read_timeout=60,
                write_timeout=60
            )
            return conn
        except Exception as e:
            self.log(f"Error connecting to MySQL database: {e}")
            return None

    def check_table_exists(self):
        """Check if the target table exists in MySQL database"""
        mysql_conn = self.connect_to_mysql_db()
        if not mysql_conn:
            return False
        
        try:
            cursor = mysql_conn.cursor()
            cursor.execute("SELECT 1 FROM access_device_logs LIMIT 1")
            cursor.fetchone()
            mysql_conn.close()
            return True
        except:
            try:
                mysql_conn.close()
            except:
                pass
            return False

    def get_new_records_from_access(self, last_timestamp=None, last_sn=None, limit=None):
        """Get new records from the checkinout table since last sync position"""
        conn = self.connect_to_access_db()
        if not conn:
            return []

        try:
            cursor = conn.cursor()
            if last_timestamp:
                if last_sn:
                    query = """
                    SELECT Badgenumber, checktime, checktype, verifycode, sensorid, workcode, sn
                    FROM checkinout
                    WHERE (checktime > ?) OR (checktime = ? AND sn > ?)
                    ORDER BY checktime, sn
                    """
                    cursor.execute(query, (last_timestamp, last_timestamp, last_sn))
                else:
                    query = """
                    SELECT Badgenumber, checktime, checktype, verifycode, sensorid, workcode, sn
                    FROM checkinout
                    WHERE checktime > ?
                    ORDER BY checktime, sn
                    """
                    cursor.execute(query, (last_timestamp,))
            else:
                query = """
                SELECT Badgenumber, checktime, checktype, verifycode, sensorid, workcode, sn
                FROM checkinout
                ORDER BY checktime, sn
                """
                cursor.execute(query)

            if limit:
                records = []
                for i, row in enumerate(cursor.fetchall()):
                    if i >= limit:
                        break
                    records.append(row)
            else:
                records = cursor.fetchall()

            conn.close()
            return records
        except Exception as e:
            self.log(f"Error querying Access database: {e}")
            if conn:
                try:
                    conn.close()
                except:
                    pass
            return []

    def sync_records_to_cloud(self, access_records):
        """Sync records from Access to MySQL cloud database"""
        if not access_records:
            return 0

        mysql_conn = self.connect_to_mysql_db()
        if not mysql_conn:
            return 0

        try:
            cursor = mysql_conn.cursor()
            insert_query = """
            INSERT IGNORE INTO access_device_logs
            (badge_number, check_time, check_type, verify_code, sensor_id, work_code, device_sn, raw_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """

            count = 0
            for record in access_records:
                badgenumber = record[0]
                checktime = record[1]
                checktype = record[2]
                verifycode = record[3]
                sensorid = record[4]
                workcode = record[5]
                sn = record[6]

                raw_data = f"Badge:{badgenumber}|CheckTime:{checktime}|Type:{checktype}|Verify:{verifycode}|Sensor:{sensorid}|WorkCode:{workcode}|SN:{sn}"

                values = (
                    str(badgenumber) if badgenumber else '',
                    str(checktime) if checktime else None,
                    str(checktype) if checktype else '',
                    str(verifycode) if verifycode else '',
                    str(sensorid) if sensorid else '',
                    str(workcode) if workcode else '',
                    str(sn) if sn else 'HIP_ACCESS_DB',
                    raw_data
                )
                cursor.execute(insert_query, values)
                count += 1

            mysql_conn.commit()
            return count

        except Exception as e:
            self.log(f"Error syncing to MySQL: {e}")
            return 0
        finally:
            try:
                if 'cursor' in locals():
                    cursor.close()
            except:
                pass
            try:
                if mysql_conn:
                    mysql_conn.close()
            except:
                pass

    def run_sync_cycle(self):
        """Runs a complete sync cycle. Returns total uploaded records."""
        # Check table
        if not self.check_table_exists():
            self.log("ERROR: access_device_logs table does not exist in MySQL!")
            return 0

        last_timestamp, last_sn = self.get_last_sync_position()
        
        # Get all new records
        all_records = self.get_new_records_from_access(last_timestamp, last_sn)
        total_records = len(all_records)

        if total_records == 0:
            self.log("No new records found in Access database")
            return 0

        config = self.load_config()
        batch_size = config.get("BATCH_SIZE", 100)
        self.log(f"Found {total_records} new records. Processing in batches of {batch_size}...")

        total_uploaded = 0
        for i in range(0, total_records, batch_size):
            if self.paused:
                self.log("Sync paused by user.")
                break
                
            batch = all_records[i:i + batch_size]
            batch_uploaded = self.sync_records_to_cloud(batch)
            total_uploaded += batch_uploaded
            
            self.log(f"Batch {i//batch_size + 1}: {batch_uploaded} records uploaded")

            if batch:
                last_record = batch[-1]
                batch_last_timestamp = str(last_record[1])
                batch_last_sn = str(last_record[6]) if last_record[6] else 'UNKNOWN'
                self.set_last_sync_position(batch_last_timestamp, batch_last_sn)
                self.log(f"Updated sync position: {batch_last_timestamp}|{batch_last_sn}")

            time.sleep(0.1) # Breathe

        self.log(f"Sync cycle completed. Total: {total_uploaded}")
        return total_uploaded
