import os
import glob
import shutil
import mysql.connector
import time
import sys
from datetime import datetime, timedelta

# ==========================================
#        USER CONFIGURATION SECTION
# ==========================================

# 1. PATHS
LOG_DIR = r"D:\Program Files (x86)\HIPPremiumTime-2.0.4\alog"
PROCESSED_DIR = os.path.join(LOG_DIR, "processed")

# 2. CLOUD DATABASE
DB_CONFIG = {
    'user': 'apis_misuzu2',
    'password': 'Tw0NC35pu*',
    'host': 'mysql.us.cloudlogin.co',
    'database': 'apis_misuzu2',
    'port': 3306,
    'raise_on_warnings': True,
    'connection_timeout': 60
}

# 3. SCHEDULER
# List the times you want the upload to happen (24-hour format)
UPLOAD_TIMES = ["09:00", "12:00", "17:00", "22:00"]

# 4. FILTER OLD DATA
# Files created before this date will be moved to processed WITHOUT uploading.
# Format: YYYY-MM-DD. Set to None to upload everything.
IGNORE_FILES_BEFORE = "2025-01-14"

# ==========================================

if not os.path.exists(PROCESSED_DIR):
    os.makedirs(PROCESSED_DIR)

def log_msg(message):
    print(f"[{datetime.now()}] {message}")
    sys.stdout.flush()

def should_process_file(file_path):
    if not IGNORE_FILES_BEFORE:
        return True

    cutoff = datetime.strptime(IGNORE_FILES_BEFORE, "%Y-%m-%d")
    # Get file creation time
    ctime = os.path.getctime(file_path)
    file_date = datetime.fromtimestamp(ctime)

    if file_date < cutoff:
        return False
    return True

def sync_logs():
    files = glob.glob(os.path.join(LOG_DIR, "*.txt"))
    if not files:
        return

    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        add_log = ("INSERT IGNORE INTO device_logs "
                   "(device_sn, user_id, check_time, status, verify_type, raw_data) "
                   "VALUES (%s, %s, %s, %s, %s, %s)")

        for file_path in files:
            filename = os.path.basename(file_path)

            # CHECK: Should we ignore this old file?
            if not should_process_file(file_path):
                log_msg(f"Skipping old file: {filename}")
                try:
                    shutil.move(file_path, os.path.join(PROCESSED_DIR, filename))
                except: pass
                continue

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
    log_msg(f"--- Service Started. Schedule: {UPLOAD_TIMES} ---")

    # Track the last minute we ran to avoid double-running in the same minute
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
