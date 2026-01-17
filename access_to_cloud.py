import os
import pyodbc
import pymysql
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
            "ACCESS_DB_PATH": "D:\\\\Program Files (x86)\\\\HIPPremiumTime-2.0.4\\\\db\\\\Pm2014.mdb",
            "ACCESS_PASSWORD": "hippmforyou",
            "UPLOAD_TIMES": ["09:00", "12:00", "17:00", "22:00"],  # Scheduled sync times
            "LAST_SYNC_FILE": "last_sync_access.txt",  # File to store last sync timestamp
            "BATCH_SIZE": 100  # Number of records to process in each batch
        }
        save_config(default_config)
        return default_config
    except Exception as e:
        print(f"Error loading config: {e}")
        # Return default config if there's an error
        return {
            "ACCESS_DB_PATH": "D:\\\\Program Files (x86)\\\\HIPPremiumTime-2.0.4\\\\db\\\\Pm2014.mdb",
            "ACCESS_PASSWORD": "hippmforyou",
            "UPLOAD_TIMES": ["09:00", "12:00", "17:00", "22:00"],
            "LAST_SYNC_FILE": "last_sync_access.txt",
            "BATCH_SIZE": 100
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

def get_last_sync_position():
    """Get the last sync position (timestamp and SN) from file"""
    try:
        with open(load_config().get("LAST_SYNC_FILE", "last_sync_access.txt"), 'r') as f:
            content = f.read().strip()
            if '|' in content:
                timestamp_part, sn_part = content.rsplit('|', 1)
                return timestamp_part, sn_part
            else:
                return content, None
    except FileNotFoundError:
        return None, None

def set_last_sync_position(timestamp, sn):
    """Save the last sync position (timestamp and SN) to file"""
    with open(load_config().get("LAST_SYNC_FILE", "last_sync_access.txt"), 'w') as f:
        f.write(f"{timestamp}|{sn}")

# Load configuration and credentials
config = load_config()
credentials = load_encrypted_credentials()

# Extract configuration values
ACCESS_DB_PATH = config.get("ACCESS_DB_PATH", "D:\\\\Program Files (x86)\\\\HIPPremiumTime-2.0.4\\\\db\\\\Pm2014.mdb")
ACCESS_PASSWORD = config.get("ACCESS_PASSWORD", "hippmforyou")
UPLOAD_TIMES = config.get("UPLOAD_TIMES", ["09:00", "12:00", "17:00", "22:00"])  # Scheduled times
BATCH_SIZE = config.get("BATCH_SIZE", 100)

def log_msg(message):
    print(f"[{datetime.now()}] {message}")
    sys.stdout.flush()

def connect_to_access_db():
    """Connect to the MS Access database"""
    try:
        # Connection string for MS Access database with password
        conn_str = (
            r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
            f"DBQ={ACCESS_DB_PATH};"
            f"PWD={ACCESS_PASSWORD}"
        )
        conn = pyodbc.connect(conn_str)
        return conn
    except Exception as e:
        log_msg(f"Error connecting to Access database: {e}")
        return None

def connect_to_mysql_db():
    """Connect to the MySQL cloud database"""
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
        log_msg(f"Error connecting to MySQL database: {e}")
        return None

def check_table_exists():
    """Check if the target table exists in MySQL database"""
    mysql_conn = connect_to_mysql_db()
    if not mysql_conn:
        return False

    try:
        cursor = mysql_conn.cursor()
        cursor.execute("SELECT 1 FROM access_device_logs LIMIT 1")
        cursor.fetchone()
        mysql_conn.close()
        return True
    except:
        mysql_conn.close()
        return False

def get_new_records_from_access(last_timestamp=None, last_sn=None, limit=None):
    """Get new records from the checkinout table since last sync position"""
    conn = connect_to_access_db()
    if not conn:
        return []

    try:
        cursor = conn.cursor()

        if last_timestamp:
            if last_sn:
                # Get records newer than last sync position (timestamp + SN)
                query = """
                SELECT Badgenumber, checktime, checktype, verifycode, sensorid, workcode, sn
                FROM checkinout
                WHERE (checktime > ?) OR (checktime = ? AND sn > ?)
                ORDER BY checktime, sn
                """
                cursor.execute(query, (last_timestamp, last_timestamp, last_sn))
            else:
                # Get records newer than last timestamp only
                query = """
                SELECT Badgenumber, checktime, checktype, verifycode, sensorid, workcode, sn
                FROM checkinout
                WHERE checktime > ?
                ORDER BY checktime, sn
                """
                cursor.execute(query, (last_timestamp,))
        else:
            # Get all records (first sync)
            query = """
            SELECT Badgenumber, checktime, checktype, verifycode, sensorid, workcode, sn
            FROM checkinout
            ORDER BY checktime, sn
            """
            cursor.execute(query)

        if limit:
            # Limit the results
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
        log_msg(f"Error querying Access database: {e}")
        if conn:
            conn.close()
        return []

def sync_records_to_cloud(access_records):
    """Sync records from Access to MySQL cloud database"""
    if not access_records:
        return 0

    # Check if target table exists
    if not check_table_exists():
        log_msg("ERROR: access_device_logs table does not exist in MySQL database!")
        log_msg("Please create the table using create_access_table.sql before running sync.")
        return 0

    mysql_conn = connect_to_mysql_db()
    if not mysql_conn:
        return 0

    try:
        cursor = mysql_conn.cursor()

        # Prepare INSERT statement for the new access_device_logs table
        insert_query = """
        INSERT IGNORE INTO access_device_logs
        (badge_number, check_time, check_type, verify_code, sensor_id, work_code, device_sn, raw_data)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        count = 0
        for record in access_records:
            # Extract Access fields
            badgenumber = record[0]  # Badgenumber
            checktime = record[1]    # checktime
            checktype = record[2]    # checktype
            verifycode = record[3]   # verifycode
            sensorid = record[4]     # sensorid
            workcode = record[5]     # workcode
            sn = record[6]           # sn

            # Format raw data string
            raw_data = f"Badge:{badgenumber}|CheckTime:{checktime}|Type:{checktype}|Verify:{verifycode}|Sensor:{sensorid}|WorkCode:{workcode}|SN:{sn}"

            # Map to MySQL fields
            values = (
                str(badgenumber) if badgenumber else '',  # badge_number
                str(checktime) if checktime else None,    # check_time
                str(checktype) if checktype else '',      # check_type
                str(verifycode) if verifycode else '',    # verify_code
                str(sensorid) if sensorid else '',        # sensor_id
                str(workcode) if workcode else '',        # work_code
                str(sn) if sn else 'HIP_ACCESS_DB',       # device_sn
                raw_data                                   # raw_data
            )

            cursor.execute(insert_query, values)
            count += 1

        mysql_conn.commit()
        log_msg(f"Uploaded {count} records to cloud database")
        return count

    except Exception as e:
        log_msg(f"Error syncing to MySQL: {e}")
        return 0
    finally:
        if mysql_conn and mysql_conn.is_connected():
            mysql_conn.close()

def sync_from_access_to_cloud():
    """Main sync function with batching and per-batch sync position updates"""
    log_msg("Starting sync from MS Access to Cloud...")

    # Check if target table exists first
    if not check_table_exists():
        log_msg("ERROR: access_device_logs table does not exist in MySQL database!")
        log_msg("Please create the table using create_access_table.sql before running sync.")
        return 0

    # Get last sync position
    last_timestamp, last_sn = get_last_sync_position()

    # Get total count first
    all_records = get_new_records_from_access(last_timestamp, last_sn)
    total_records = len(all_records)
    
    if total_records == 0:
        log_msg("No new records found in Access database")
        return 0

    log_msg(f"Found {total_records} new records in Access database. Processing in batches of {BATCH_SIZE}...")

    # Process in batches
    total_uploaded = 0
    for i in range(0, total_records, BATCH_SIZE):
        batch = all_records[i:i + BATCH_SIZE]
        batch_uploaded = sync_records_to_cloud(batch)
        total_uploaded += batch_uploaded
        
        log_msg(f"Processed batch {i//BATCH_SIZE + 1}: {batch_uploaded} records uploaded")
        
        # Update last sync position after each batch with the last record's position
        if batch:
            last_record = batch[-1]  # Get the last record in this batch
            batch_last_timestamp = str(last_record[1])  # checktime is at index 1
            batch_last_sn = str(last_record[6]) if last_record[6] else 'UNKNOWN'  # sn is at index 6
            set_last_sync_position(batch_last_timestamp, batch_last_sn)
            log_msg(f"Updated sync position to: {batch_last_timestamp}|{batch_last_sn}")
        
        # Small delay between batches to avoid overwhelming the database
        time.sleep(0.1)

    log_msg(f"Sync completed. Total uploaded: {total_uploaded} records.")
    return total_uploaded

if __name__ == "__main__":
    log_msg("=== MS Access to Cloud Sync Service Started ===")
    log_msg(f"Access DB: {ACCESS_DB_PATH}")
    log_msg(f"Schedule: {UPLOAD_TIMES}")  # Show the scheduled times like the original
    log_msg(f"Batch size: {BATCH_SIZE} records")

    # Check if credentials are loaded
    log_msg(f"Credential status: {'LOADED' if credentials else 'FAILED TO LOAD'}")

    # Check if target table exists before proceeding
    if not check_table_exists():
        log_msg("WARNING: access_device_logs table does not exist in MySQL database!")
        log_msg("Please create the table using create_access_table.sql before running sync.")
        sys.exit(1)
    else:
        log_msg("INFO: Target table exists in MySQL database")

    try:
        # For continuous operation with scheduled times (like original sync_to_cloud.py)
        log_msg("--- Starting scheduled sync mode ---")
        last_run_minute = None

        while True:
            now = datetime.now()
            current_time = now.strftime("%H:%M")

            # Log current time for debugging
            log_msg(f"DEBUG: Current time is {current_time}, checking against schedule: {UPLOAD_TIMES}")

            # Check if current time matches schedule
            if current_time in UPLOAD_TIMES:
                if current_time != last_run_minute:
                    log_msg(f"Scheduled time reached ({current_time}). Starting sync...")
                    sync_from_access_to_cloud()
                    last_run_minute = current_time
                else:
                    log_msg(f"DEBUG: Time {current_time} already processed in this minute, skipping")
            else:
                log_msg(f"DEBUG: Current time {current_time} not in schedule, continuing...")

            # Sleep for 30 seconds to spare CPU
            time.sleep(30)

    except KeyboardInterrupt:
        log_msg("Sync service interrupted by user")
    except Exception as e:
        log_msg(f"Error in sync service: {e}")
        import traceback
        traceback.print_exc()

    log_msg("=== MS Access to Cloud Sync Service Ended ===")