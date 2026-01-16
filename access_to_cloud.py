import os
import pyodbc
import mysql.connector
import time
import sys
from datetime import datetime, timedelta
import json

# Configuration files
CONFIG_FILE = "config.json"
CREDENTIALS_FILE = "credentials.json"

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
            "SYNC_INTERVAL": 300,  # Sync every 5 minutes
            "LAST_SYNC_FILE": "last_sync.txt"  # File to store last sync timestamp
        }
        save_config(default_config)
        return default_config
    except Exception as e:
        print(f"Error loading config: {e}")
        # Return default config if there's an error
        return {
            "ACCESS_DB_PATH": "D:\\\\Program Files (x86)\\\\HIPPremiumTime-2.0.4\\\\db\\\\Pm2014.mdb",
            "ACCESS_PASSWORD": "hippmforyou",
            "SYNC_INTERVAL": 300,
            "LAST_SYNC_FILE": "last_sync.txt"
        }

def load_credentials():
    """Load private credentials from JSON file"""
    try:
        with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
            creds = json.load(f)
            return creds.get("DB_CONFIG", {})
    except FileNotFoundError:
        print(f"Credentials file {CREDENTIALS_FILE} not found!")
        return {}
    except Exception as e:
        print(f"Error loading credentials: {e}")
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

def get_last_sync_time():
    """Get the last sync time from file"""
    try:
        with open(load_config().get("LAST_SYNC_FILE", "last_sync.txt"), 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def set_last_sync_time(sync_time):
    """Save the last sync time to file"""
    with open(load_config().get("LAST_SYNC_FILE", "last_sync.txt"), 'w') as f:
        f.write(sync_time)

# Load configuration and credentials
config = load_config()
credentials = load_credentials()

# Extract configuration values
ACCESS_DB_PATH = config.get("ACCESS_DB_PATH", "D:\\\\Program Files (x86)\\\\HIPPremiumTime-2.0.4\\\\db\\\\Pm2014.mdb")
ACCESS_PASSWORD = config.get("ACCESS_PASSWORD", "hippmforyou")
SYNC_INTERVAL = config.get("SYNC_INTERVAL", 300)  # Default to 5 minutes

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
        conn = mysql.connector.connect(**credentials)
        return conn
    except Exception as e:
        log_msg(f"Error connecting to MySQL database: {e}")
        return None

def get_new_records_from_access(last_sync_time=None):
    """Get new records from the checkinout table since last sync"""
    conn = connect_to_access_db()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        
        if last_sync_time:
            # Get records newer than last sync time
            query = """
            SELECT Badgenumber, checktime, checktype, verifycode, sensorid, workcode, sn
            FROM checkinout
            WHERE checktime > ?
            ORDER BY checktime
            """
            cursor.execute(query, (last_sync_time,))
        else:
            # Get all records (first sync)
            query = """
            SELECT Badgenumber, checktime, checktype, verifycode, sensorid, workcode, sn
            FROM checkinout
            ORDER BY checktime
            """
            cursor.execute(query)
        
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
    
    mysql_conn = connect_to_mysql_db()
    if not mysql_conn:
        return 0
    
    try:
        cursor = mysql_conn.cursor()
        
        # Prepare INSERT statement for MySQL
        insert_query = """
        INSERT IGNORE INTO device_logs 
        (device_sn, user_id, check_time, status, verify_type, raw_data) 
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        count = 0
        for record in access_records:
            # Map Access fields to MySQL fields
            badgenumber = record[0]  # Badgenumber -> user_id
            checktime = record[1]    # checktime -> check_time
            checktype = record[2]    # checktype (could map to status)
            verifycode = record[3]   # verifycode -> verify_type
            sensorid = record[4]     # sensorid (could include in raw_data)
            workcode = record[5]     # workcode (could include in raw_data)
            sn = record[6]           # sn -> device_sn
            
            # Format raw data string
            raw_data = f"Badge:{badgenumber}|CheckTime:{checktime}|Type:{checktype}|Verify:{verifycode}|Sensor:{sensorid}|WorkCode:{workcode}|SN:{sn}"
            
            # Map to MySQL fields
            values = (
                str(sn) if sn else 'HIP_ACCESS_DB',  # device_sn
                str(badgenumber) if badgenumber else '',  # user_id
                str(checktime) if checktime else None,    # check_time
                str(checktype) if checktype else '0',     # status
                str(verifycode) if verifycode else '1',   # verify_type
                raw_data  # raw_data
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
    """Main sync function"""
    log_msg("Starting sync from MS Access to Cloud...")
    
    # Get last sync time
    last_sync_time = get_last_sync_time()
    
    # Get new records from Access
    access_records = get_new_records_from_access(last_sync_time)
    
    if not access_records:
        log_msg("No new records found in Access database")
        return 0
    
    log_msg(f"Found {len(access_records)} new records in Access database")
    
    # Sync to cloud
    uploaded_count = sync_records_to_cloud(access_records)
    
    # Update last sync time to the latest record's time
    if access_records:
        latest_time = max(record[1] for record in access_records)  # checktime is at index 1
        set_last_sync_time(str(latest_time))
        log_msg(f"Updated last sync time to: {latest_time}")
    
    log_msg(f"Sync completed. Uploaded {uploaded_count} records.")
    return uploaded_count

if __name__ == "__main__":
    log_msg("=== MS Access to Cloud Sync Service Started ===")
    log_msg(f"Access DB: {ACCESS_DB_PATH}")
    log_msg(f"Sync interval: {SYNC_INTERVAL} seconds")
    
    # For testing, run one sync immediately
    try:
        sync_from_access_to_cloud()
        log_msg("Initial sync completed.")
        
        # For continuous operation, uncomment the following lines:
        # while True:
        #     sync_from_access_to_cloud()
        #     time.sleep(SYNC_INTERVAL)
            
    except KeyboardInterrupt:
        log_msg("Sync service interrupted by user")
    except Exception as e:
        log_msg(f"Error in sync service: {e}")
        import traceback
        traceback.print_exc()
    
    log_msg("=== MS Access to Cloud Sync Service Ended ===")