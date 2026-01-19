import os
import pymysql
import time
import sys
from datetime import datetime
import json
from cryptography.fernet import Fernet

# Try to import access_parser
try:
    from access_parser import AccessParser
except ImportError:
    print("ERROR: 'access-parser' library is missing.")
    print("Please install it using: pip install access-parser")
    sys.exit(1)

# Configuration files
CONFIG_FILE = "config.json"
ENCRYPTED_CREDENTIALS_FILE = "encrypted_credentials.bin"

def load_config():
    """Load public configuration from JSON file"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # Default config
        return {
            "ACCESS_DB_PATH": "D:\\Program Files (x86)\\HIPPremiumTime-2.0.4\\db\\Pm2014.mdb",
            "UPLOAD_TIMES": ["09:00", "12:00", "17:00", "22:00"],
            "LAST_SYNC_FILE": "last_sync_access_pure.txt",
            "BATCH_SIZE": 100
        }
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

def load_encrypted_credentials():
    """Load and decrypt credentials from encrypted file"""
    try:
        # Fixed encryption key
        ENCRYPTION_KEY = b'XZgpn7Se8pQeHY8RMyeYf6e5Twq9PdOBVo9JPsqHZA4='

        with open(ENCRYPTED_CREDENTIALS_FILE, 'rb') as f:
            encrypted_data = f.read()

        fernet = Fernet(ENCRYPTION_KEY)
        decrypted_data = fernet.decrypt(encrypted_data)
        credentials = json.loads(decrypted_data.decode())
        return credentials.get("DB_CONFIG", {})
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
        filename = load_config().get("LAST_SYNC_FILE", "last_sync_access_pure.txt")
        with open(filename, 'r') as f:
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
    filename = load_config().get("LAST_SYNC_FILE", "last_sync_access_pure.txt")
    with open(filename, 'w') as f:
        f.write(f"{timestamp}|{sn}")

# Load configuration and credentials
config = load_config()
credentials = load_encrypted_credentials()

# Extract configuration values
ACCESS_DB_PATH = config.get("ACCESS_DB_PATH", "D:\\Program Files (x86)\\HIPPremiumTime-2.0.4\\db\\Pm2014.mdb")
UPLOAD_TIMES = config.get("UPLOAD_TIMES", ["09:00", "12:00", "17:00", "22:00"])
BATCH_SIZE = config.get("BATCH_SIZE", 100)

def log_msg(message):
    print(f"[{datetime.now()}] {message}")
    sys.stdout.flush()

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

def parse_access_records_pure(last_timestamp=None, last_sn=None):
    """
    Get new records from the checkinout table using pure python parser.
    This reads the whole table and filters in memory.
    """
    if not os.path.exists(ACCESS_DB_PATH):
        log_msg(f"Error: Database file not found at {ACCESS_DB_PATH}")
        return []

    try:
        # Initialize the parser
        # Note: access_parser typically ignores standard passwords as it reads raw structure
        db = AccessParser(ACCESS_DB_PATH)
        
        # Parse the checkinout table
        # access_parser returns a generator of dicts
        log_msg("Reading Access database (Pure Python)...")
        table = db.parse_table("checkinout")
        
        records = []
        
        for row in table:
            # Field names in access_parser are usually keys in the dict
            # We need to map them. Keys might be case-sensitive depending on the lib version, usually matches DB.
            # Convert keys to lowercase for safer lookup if needed, or check structure.
            # Assuming standard HIP column names: Badgenumber, checktime, checktype, verifycode, sensorid, workcode, sn
            
            # Helper to safely get value regardless of case
            def get_val(r, key):
                for k in r.keys():
                    if k.lower() == key.lower():
                        return r[k]
                return None

            checktime_str = get_val(row, 'checktime')
            sn = get_val(row, 'sn')
            
            # Convert checktime to datetime object if it's a string, or ensure it's comparable
            # access_parser usually returns datetime objects for date fields
            checktime_dt = None
            if checktime_str:
                if isinstance(checktime_str, datetime):
                    checktime_dt = checktime_str
                else:
                    try:
                        # Attempt common formats
                        checktime_dt = datetime.strptime(str(checktime_str), "%Y-%m-%d %H:%M:%S")
                    except:
                        pass

            if not checktime_dt:
                continue

            # Filtering Logic
            is_new = False
            
            if last_timestamp is None:
                is_new = True
            else:
                # Convert last_timestamp to datetime for comparison
                try:
                    last_dt = datetime.strptime(str(last_timestamp), "%Y-%m-%d %H:%M:%S")
                except:
                    last_dt = datetime.min

                if checktime_dt > last_dt:
                    is_new = True
                elif checktime_dt == last_dt:
                    # If timestamps are equal, check SN
                    # Convert SNs to integers for comparison if possible
                    try:
                        curr_sn_int = int(sn) if sn else 0
                        last_sn_int = int(last_sn) if last_sn else 0
                        if curr_sn_int > last_sn_int:
                            is_new = True
                    except:
                        pass
            
            if is_new:
                # Store as tuple to match previous structure:
                # (Badgenumber, checktime, checktype, verifycode, sensorid, workcode, sn)
                records.append((
                    get_val(row, 'Badgenumber'),
                    checktime_dt,
                    get_val(row, 'checktype'),
                    get_val(row, 'verifycode'),
                    get_val(row, 'sensorid'),
                    get_val(row, 'workcode'),
                    sn
                ))

        # Sort records by time then SN
        records.sort(key=lambda x: (x[1], int(x[6]) if x[6] and str(x[6]).isdigit() else 0))
        
        return records

    except Exception as e:
        log_msg(f"Error parsing Access database: {e}")
        import traceback
        traceback.print_exc()
        return []

def sync_records_to_cloud(access_records):
    """Sync records from Access to MySQL cloud database"""
    if not access_records:
        return 0

    if not check_table_exists():
        log_msg("ERROR: access_device_logs table does not exist in MySQL database!")
        return 0

    mysql_conn = connect_to_mysql_db()
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

            # Format datetime for string storage/raw data
            checktime_str = checktime.strftime("%Y-%m-%d %H:%M:%S") if isinstance(checktime, datetime) else str(checktime)

            raw_data = f"Badge:{badgenumber}|CheckTime:{checktime_str}|Type:{checktype}|Verify:{verifycode}|Sensor:{sensorid}|WorkCode:{workcode}|SN:{sn}"

            values = (
                str(badgenumber) if badgenumber else '',
                checktime_str,
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
        log_msg(f"Error syncing to MySQL: {e}")
        return 0
    finally:
        if mysql_conn and mysql_conn.is_connected():
            mysql_conn.close()

def sync_from_access_to_cloud():
    """Main sync function"""
    log_msg("Starting sync from MS Access (Pure Python Mode)...")

    # Get last sync position
    last_timestamp, last_sn = get_last_sync_position()

    # Get all new records (read filtered from full table scan)
    all_records = parse_access_records_pure(last_timestamp, last_sn)
    total_records = len(all_records)
    
    if total_records == 0:
        log_msg("No new records found.")
        return 0

    log_msg(f"Found {total_records} new records. Processing in batches of {BATCH_SIZE}...")

    total_uploaded = 0
    for i in range(0, total_records, BATCH_SIZE):
        batch = all_records[i:i + BATCH_SIZE]
        batch_uploaded = sync_records_to_cloud(batch)
        total_uploaded += batch_uploaded
        
        log_msg(f"Processed batch {i//BATCH_SIZE + 1}: {batch_uploaded} records uploaded")
        
        if batch:
            last_record = batch[-1]
            # timestamp is at index 1 (datetime object)
            batch_last_timestamp = last_record[1].strftime("%Y-%m-%d %H:%M:%S")
            batch_last_sn = str(last_record[6]) if last_record[6] else 'UNKNOWN'
            set_last_sync_position(batch_last_timestamp, batch_last_sn)
            log_msg(f"Updated sync position to: {batch_last_timestamp}|{batch_last_sn}")
        
        time.sleep(0.1)

    log_msg(f"Sync completed. Total uploaded: {total_uploaded} records.")
    return total_uploaded

if __name__ == "__main__":
    log_msg("=== HIP Access to Cloud Sync (Pure Python Mode) ===")
    log_msg(f"Access DB: {ACCESS_DB_PATH}")
    log_msg("Note: This mode bypasses ODBC drivers.")

    # Main loop
    try:
        log_msg("--- Starting scheduled sync mode ---")
        last_run_minute = None

        while True:
            now = datetime.now()
            current_time = now.strftime("%H:%M")

            if current_time in UPLOAD_TIMES:
                if current_time != last_run_minute:
                    log_msg(f"Scheduled time reached ({current_time}). Starting sync...")
                    sync_from_access_to_cloud()
                    last_run_minute = current_time
            
            time.sleep(30)

    except KeyboardInterrupt:
        log_msg("Sync service interrupted by user")
    except Exception as e:
        log_msg(f"Error in sync service: {e}")
