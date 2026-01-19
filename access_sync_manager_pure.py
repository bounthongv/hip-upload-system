import os
import json
import time
import sys
from datetime import datetime
import pymysql
import traceback
from cryptography.fernet import Fernet

# Global flag to track if import succeeded
ACCESS_PARSER_AVAILABLE = False
IMPORT_ERROR_MSG = ""

try:
    from access_parser import AccessParser
    ACCESS_PARSER_AVAILABLE = True
except ImportError as e:
    IMPORT_ERROR_MSG = f"{e}\n{traceback.format_exc()}"
    print(f"CRITICAL: access-parser import failed: {IMPORT_ERROR_MSG}")

class PureAccessSyncManager:
    """
    Manages the synchronization logic between MS Access and MySQL Cloud
    using 'access-parser' (Pure Python) to avoid ODBC driver issues.
    """
    
    ENCRYPTION_KEY = b'XZgpn7Se8pQeHY8RMyeYf6e5Twq9PdOBVo9JPsqHZA4='

    def __init__(self, config_file="config.json", cred_file="encrypted_credentials.bin", logger_callback=None):
        self.config_file = config_file
        self.cred_file = cred_file
        self.logger_callback = logger_callback if logger_callback else self._default_logger
        self.paused = False
        self.running = False

    def _default_logger(self, message):
        print(f"[{datetime.now()}] {message}")
        sys.stdout.flush()

    def log(self, message):
        self.logger_callback(message)

    def load_config(self):
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return self._get_default_config()
        except Exception as e:
            self.log(f"Error loading config: {e}")
            return self._get_default_config()

    def _get_default_config(self):
        return {
            "ACCESS_DB_PATH": "D:\\Program Files (x86)\\HIPPremiumTime-2.0.4\\db\\Pm2014.mdb",
            "UPLOAD_TIMES": ["09:00", "12:00", "17:00", "22:00"],
            "LAST_SYNC_FILE": "last_sync_access_pure.txt",
            "BATCH_SIZE": 100
        }

    def save_config(self, config):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            self.log(f"Error saving config: {e}")
            return False

    def load_encrypted_credentials(self):
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
        config = self.load_config()
        last_sync_file = config.get("LAST_SYNC_FILE", "last_sync_access_pure.txt")
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
        config = self.load_config()
        last_sync_file = config.get("LAST_SYNC_FILE", "last_sync_access_pure.txt")
        try:
            with open(last_sync_file, 'w') as f:
                f.write(f"{timestamp}|{sn}")
        except Exception as e:
            self.log(f"Error saving sync position: {e}")

    def connect_to_mysql_db(self):
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
                connect_timeout=60
            )
            return conn
        except Exception as e:
            self.log(f"Error connecting to MySQL database: {e}")
            return None

    def check_table_exists(self):
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

    def get_new_records_from_access(self, last_timestamp=None, last_sn=None):
        """
        Reads records using access-parser and filters for new ones.
        Returns a list of tuples.
        """
        config = self.load_config()
        db_path = config.get("ACCESS_DB_PATH", self._get_default_config()["ACCESS_DB_PATH"])

        if not os.path.exists(db_path):
            self.log(f"Error: Database file not found at {db_path}")
            return []

        if not ACCESS_PARSER_AVAILABLE:
            self.log(f"ERROR: Cannot parse database. 'access-parser' library failed to load.")
            self.log(f"Debug Details: {IMPORT_ERROR_MSG}")
            return []

        try:
            self.log("Reading Access database (Pure Python)...")
            db = AccessParser(db_path)
            found_tables = db.catalog.keys()
            
            # Case-insensitive lookup for table name
            target_table = "checkinout"
            actual_table_name = None
            for tbl in found_tables:
                if tbl.lower() == target_table.lower():
                    actual_table_name = tbl
                    break
            
            if not actual_table_name:
                self.log(f"ERROR: Table '{target_table}' not found in database!")
                return []
                
            self.log(f"Parsing table: {actual_table_name}")
            table = db.parse_table(actual_table_name)
            
            # Map expected fields to actual column names in the defaultdict
            # Structure is table[column_name] = {row_index: value} or [values] ? 
            # access-parser usually returns dict of dicts {col: {row_idx: val}} or dict of lists.
            # Let's check the type of values in the first column to be safe, or just assume dict-like behavior based on keys.
            
            # We need to find the specific keys for our columns
            expected_cols = {
                'badgenumber': None,
                'checktime': None, 
                'checktype': None, 
                'verifycode': None, 
                'sensorid': None, 
                'workcode': None, 
                'sn': None
            }
            
            for col_name in table.keys():
                lower_name = col_name.lower()
                if lower_name in expected_cols:
                    expected_cols[lower_name] = col_name
            
            # Determine number of rows based on the first found column
            num_rows = 0
            first_col = next((c for c in expected_cols.values() if c is not None), None)
            
            if first_col and isinstance(table[first_col], dict):
                # If it's a dict {row_idx: val}, get max key
                if table[first_col]:
                    num_rows = max(table[first_col].keys()) + 1
            elif first_col and isinstance(table[first_col], list):
                num_rows = len(table[first_col])
            
            self.log(f"Detected {num_rows} rows in table.")

            records = []
            
            for i in range(num_rows):
                # Helper to get value for current row i
                def get_col_val(col_key):
                    actual_key = expected_cols.get(col_key)
                    if not actual_key: 
                        return None
                    
                    # Access data structure
                    col_data = table[actual_key]
                    if isinstance(col_data, dict):
                        return col_data.get(i)
                    elif isinstance(col_data, list):
                        return col_data[i] if i < len(col_data) else None
                    return None

                checktime_str = get_col_val('checktime')
                sn = get_col_val('sn')
                
                checktime_dt = None
                if checktime_str:
                    if isinstance(checktime_str, datetime):
                        checktime_dt = checktime_str
                    else:
                        try:
                            # access-parser sometimes returns strings like '2023-01-01 12:00:00'
                            checktime_dt = datetime.strptime(str(checktime_str), "%Y-%m-%d %H:%M:%S")
                        except:
                            pass

                if not checktime_dt:
                    continue

                is_new = False
                
                if last_timestamp is None:
                    is_new = True
                else:
                    try:
                        last_dt = datetime.strptime(str(last_timestamp), "%Y-%m-%d %H:%M:%S")
                    except:
                        last_dt = datetime.min

                    if checktime_dt > last_dt:
                        is_new = True
                    elif checktime_dt == last_dt:
                        try:
                            # Handle SN comparison safely
                            curr_sn_val = sn or 0
                            last_sn_val = last_sn or 0
                            
                            # Try integer comparison first
                            if str(curr_sn_val).isdigit() and str(last_sn_val).isdigit():
                                if int(curr_sn_val) > int(last_sn_val):
                                    is_new = True
                            else:
                                # Fallback to string comparison
                                if str(curr_sn_val) > str(last_sn_val):
                                    is_new = True
                        except:
                            pass
                
                if is_new:
                    records.append((
                        get_col_val('badgenumber'),
                        checktime_dt,
                        get_col_val('checktype'),
                        get_col_val('verifycode'),
                        get_col_val('sensorid'),
                        get_col_val('workcode'),
                        sn
                    ))

            # Sort records by time then SN
            records.sort(key=lambda x: (x[1], int(x[6]) if x[6] and str(x[6]).isdigit() else 0))
            
            return records

            for row in table:
                checktime_str = get_val(row, 'checktime')
                sn = get_val(row, 'sn')
                
                checktime_dt = None
                if checktime_str:
                    if isinstance(checktime_str, datetime):
                        checktime_dt = checktime_str
                    else:
                        try:
                            checktime_dt = datetime.strptime(str(checktime_str), "%Y-%m-%d %H:%M:%S")
                        except:
                            pass

                if not checktime_dt:
                    continue

                is_new = False
                
                if last_timestamp is None:
                    is_new = True
                else:
                    try:
                        last_dt = datetime.strptime(str(last_timestamp), "%Y-%m-%d %H:%M:%S")
                    except:
                        last_dt = datetime.min

                    if checktime_dt > last_dt:
                        is_new = True
                    elif checktime_dt == last_dt:
                        try:
                            curr_sn_int = int(sn) if sn else 0
                            last_sn_int = int(last_sn) if last_sn else 0
                            if curr_sn_int > last_sn_int:
                                is_new = True
                        except:
                            pass
                
                if is_new:
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
            self.log(f"Error parsing Access database: {e}")
            self.log(f"Traceback: {traceback.format_exc()}")
            return []

    def sync_records_to_cloud(self, access_records):
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
            self.log(f"Error syncing to MySQL: {e}")
            return 0
        finally:
            try:
                if mysql_conn:
                    mysql_conn.close()
            except:
                pass

    def run_sync_cycle(self):
        """Runs a complete sync cycle. Returns total uploaded records."""
        if not self.check_table_exists():
            self.log("ERROR: access_device_logs table does not exist in MySQL!")
            return 0

        last_timestamp, last_sn = self.get_last_sync_position()
        
        # Get all new records
        all_records = self.get_new_records_from_access(last_timestamp, last_sn)
        total_records = len(all_records)

        if total_records == 0:
            self.log("No new records found.")
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
                # Checktime is at index 1 (datetime object)
                batch_last_timestamp = last_record[1].strftime("%Y-%m-%d %H:%M:%S") if isinstance(last_record[1], datetime) else str(last_record[1])
                batch_last_sn = str(last_record[6]) if last_record[6] else 'UNKNOWN'
                self.set_last_sync_position(batch_last_timestamp, batch_last_sn)
                self.log(f"Updated sync position: {batch_last_timestamp}|{batch_last_sn}")

            time.sleep(0.1)

        self.log(f"Sync cycle completed. Total: {total_uploaded}")
        return total_uploaded
