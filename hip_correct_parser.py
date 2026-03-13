"""
HIP CMI F68S Complete Solution
Parses device data and stores in SQLite database for historical tracking
"""

import socket
import time
import sqlite3
from datetime import datetime, timedelta

# ================= CONFIGURATION =================
DEVICE_IP = "192.168.100.166"
DEVICE_PORT = 5005
TIMEOUT = 5
DB_FILE = "attendance.db"
# =================================================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

class AttendanceDatabase:
    """Manages SQLite database for attendance records"""

    def __init__(self, db_file):
        self.db_file = db_file
        self.init_database()

    def init_database(self):
        """Create database table if not exists"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                check_time DATETIME NOT NULL,
                verify_method TEXT,
                device_id INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, check_time, device_id)
            )
        ''')

        conn.commit()
        conn.close()
        log(f"Database initialized: {self.db_file}")

    def insert_records(self, records):
        """Insert new records, skip duplicates"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        inserted = 0
        skipped = 0

        for rec in records:
            try:
                cursor.execute('''
                    INSERT INTO attendance (user_id, check_time, verify_method)
                    VALUES (?, ?, ?)
                ''', (rec['id'], rec['datetime'].strftime('%Y-%m-%d %H:%M:%S'), rec['verify']))
                inserted += 1
            except sqlite3.IntegrityError:
                # Duplicate record, skip
                skipped += 1

        conn.commit()
        conn.close()

        return inserted, skipped

    def get_all_records(self, limit=None):
        """Get all records from database"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        query = '''
            SELECT user_id, check_time, verify_method
            FROM attendance
            ORDER BY check_time
        '''

        if limit:
            query += f' LIMIT {limit}'

        cursor.execute(query)
        records = cursor.fetchall()
        conn.close()

        return records

    def get_record_count(self):
        """Get total record count"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM attendance')
        count = cursor.fetchone()[0]
        conn.close()
        return count

class HIPParser:
    """Parses attendance data from HIP CMI F68S device"""

    def __init__(self, ip, port, start_date=None):
        self.ip = ip
        self.port = port
        self.start_date = start_date or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    def connect(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(TIMEOUT)
            sock.connect((self.ip, self.port))
            return sock
        except Exception as e:
            log(f"Connection failed: {e}")
            return None

    def fetch_data(self):
        """Fetch data from device"""
        sock = self.connect()
        if not sock:
            return b""

        try:
            # Handshake
            sock.send(bytes.fromhex("55 aa 01 b0 00 00 00 00 00 00 ff ff 00 00 17 00"))
            sock.recv(1024)

            sock.send(bytes.fromhex("55 aa 01 b4 00 00 00 00 00 00 ff ff 00 00 18 00"))
            resp = sock.recv(1024)
            token = resp[4] if len(resp) > 4 else 0x03

            # Request data
            pkt = bytearray.fromhex("55 aa 01 a4 00 00 00 00 20 00 00 00 00 00 19 00")
            pkt[7] = token
            pkt[13] = token
            sock.send(pkt)

            # Read all data
            page_data = b""
            sock.settimeout(2.0)
            try:
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    page_data += chunk
                    time.sleep(0.05)
            except socket.timeout:
                pass

            return page_data

        except Exception as e:
            log(f"Fetch error: {e}")
            return b""
        finally:
            sock.close()

    def resolve_actual_hour(self, hour_raw, prev_hour):
        """Resolve actual hour from 3-bit raw value"""
        candidates = [hour_raw, hour_raw + 8, hour_raw + 16]
        candidates = [h for h in candidates if 0 <= h < 24]

        if prev_hour is None:
            mid_range = [h for h in candidates if 8 <= h <= 15]
            return mid_range[0] if mid_range else candidates[0]

        valid = [h for h in candidates if h >= prev_hour]
        return valid[0] if valid else min(candidates)

    def parse_16byte_record(self, chunk, current_date, last_hour):
        """Parse 16-byte header record"""
        if len(chunk) < 17:
            return None

        uid = chunk[5]
        if uid not in [1, 2]:
            return None

        second = chunk[12]
        hour_raw = (chunk[15] >> 5) & 0x07
        minute = chunk[16] >> 2

        actual_hour = self.resolve_actual_hour(hour_raw, last_hour)

        try:
            dt = current_date.replace(hour=actual_hour, minute=minute, second=second)
            return {
                "id": uid,
                "datetime": dt,
                "time": dt.strftime("%d/%m/%Y %I:%M:%S %p"),
                "verify": "1 T",
                "hour": actual_hour
            }
        except:
            return None

    def parse_20byte_record(self, chunk, current_date, last_hour):
        """Parse 20-byte standard record"""
        uid = chunk[5]

        if uid not in [1, 2]:
            return None

        second = chunk[12]
        hour_raw = (chunk[15] >> 5) & 0x07
        minute = chunk[16] >> 2

        actual_hour = self.resolve_actual_hour(hour_raw, last_hour)

        try:
            dt = current_date.replace(hour=actual_hour, minute=minute, second=second)
            return {
                "id": uid,
                "datetime": dt,
                "time": dt.strftime("%d/%m/%Y %I:%M:%S %p"),
                "verify": "1 T",
                "hour": actual_hour
            }
        except:
            return None

    def parse(self, raw_data):
        """Parse all records from device buffer"""
        records = []
        seen = set()

        current_date = self.start_date
        last_hour = None

        # Parse first record at offset 7
        if len(raw_data) >= 24:
            chunk = raw_data[7:24]
            rec = self.parse_16byte_record(chunk, current_date, last_hour)
            if rec:
                time_key = rec["datetime"].strftime("%Y-%m-%d %H:%M:%S")
                seen.add((rec["id"], time_key))
                records.append(rec)
                last_hour = rec["hour"]

        # Parse 20-byte records
        i = 27
        while i < len(raw_data) - 19:
            if (raw_data[i] == 0x01 and raw_data[i+1] == 0x00 and
                raw_data[i+2] == 0x00 and raw_data[i+3] == 0x00):

                chunk = raw_data[i:i+20]
                rec = self.parse_20byte_record(chunk, current_date, last_hour)

                if rec:
                    # Check for midnight rollover
                    if last_hour is not None and rec["hour"] < last_hour - 12:
                        current_date += timedelta(days=1)
                        rec = self.parse_20byte_record(chunk, current_date, None)

                    if rec:
                        time_key = rec["datetime"].strftime("%Y-%m-%d %H:%M:%S")
                        if (rec["id"], time_key) not in seen:
                            seen.add((rec["id"], time_key))
                            records.append(rec)
                            last_hour = rec["hour"]

                i += 20
            else:
                i += 1

        records.sort(key=lambda x: x['datetime'])
        return records

def main():
    """Main function - fetch, parse, and store attendance data"""
    print("="*70)
    print("HIP CMI F68S Attendance Data Collector")
    print("="*70)

    # Initialize database
    db = AttendanceDatabase(DB_FILE)

    # Initialize parser with estimated start date
    # You might want to adjust this based on your needs
    parser = HIPParser(DEVICE_IP, DEVICE_PORT, start_date=datetime(2026, 1, 14))

    # Fetch and parse data
    log("Fetching data from device...")
    raw_data = parser.fetch_data()

    if not raw_data:
        log("ERROR: No data received from device")
        return

    log(f"Received {len(raw_data)} bytes")
    log("Parsing records...")

    records = parser.parse(raw_data)
    log(f"Parsed {len(records)} records from device buffer")

    # Store in database
    inserted, skipped = db.insert_records(records)
    log(f"Database updated: {inserted} new, {skipped} duplicates")

    # Display results
    total_records = db.get_record_count()
    print(f"\n{'='*70}")
    print(f"CURRENT DEVICE BUFFER ({len(records)} records)")
    print("="*70)
    print("No. | ID | TIME                      | VERIFY")
    print("-" * 70)

    for idx, r in enumerate(records, 1):
        print(f"{idx:3d} | {r['id']:2d} | {r['time']:24s} | {r['verify']}")

    print(f"\n{'='*70}")
    print(f"Total records in database: {total_records}")
    print(f"Last updated: {datetime.now().strftime('%d/%m/%Y %I:%M:%S %p')}")
    print("="*70)

    print("\nNOTE: Device buffer holds ~38 most recent records.")
    print("Run this script regularly (e.g., daily) to capture all attendance data")
    print("before old records are overwritten.")

if __name__ == "__main__":
    main()
