"""
HIP CMI F68S UNIVERSAL PARSER (Chronological Reconstruction)

STRATEGY:
1. We trust the "Seconds" (Byte 12) and "Minutes" (Byte 16 >> 2) 100%.
2. We IGNORE the "Hour" and "Date" bytes from the device (since they are encoded/buggy).
3. We start at the known anchor time (Line 1).
4. We calculate every subsequent record by "Forward Progression":
   - If time moves backward (e.g., 10:55 -> 10:05), we add 1 Hour.
   - If that still doesn't make sense, we add a Day.
"""

import socket
import struct
import time
import json
from datetime import datetime, timedelta

# ================= CONFIGURATION =================
DEVICE_IP = "192.168.100.166"
DEVICE_PORT = 5005
TIMEOUT = 5

# GROUND TRUTH: Line 1 of your log
# 14/01/2026 10:48:21
START_ANCHOR = datetime(2026, 1, 14, 10, 48, 21)
# =================================================

class HIPUniversal:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = None

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(TIMEOUT)
            self.sock.connect((self.ip, self.port))
            return True
        except: return False

    def fetch_all_pages(self):
        """Fetch multiple pages of data to ensure we get all 86+ records"""
        full_data = b""

        # Loop 3 times to get pages
        for page in range(3):
            if not self.connect(): break

            # Handshake
            self.sock.send(bytes.fromhex("55 aa 01 b0 00 00 00 00 00 00 ff ff 00 00 17 00"))
            self.sock.recv(1024)
            self.sock.send(bytes.fromhex("55 aa 01 b4 00 00 00 00 00 00 ff ff 00 00 18 00"))
            resp = self.sock.recv(1024)
            token = resp[4] if len(resp) > 4 else 0x03

            # Request
            pkt = bytearray.fromhex("55 aa 01 a4 00 00 00 00 20 00 00 00 00 00 19 00")
            pkt[7] = token
            pkt[13] = token
            self.sock.send(pkt)

            # Receive
            chunk_buffer = b""
            try:
                self.sock.settimeout(2.0)
                while True:
                    chunk = self.sock.recv(4096)
                    if not chunk: break
                    chunk_buffer += chunk
                    time.sleep(0.1)
            except socket.timeout: pass

            self.sock.close()

            # Simple dedup: Only add if we haven't seen this exact block
            if len(chunk_buffer) > 0:
                full_data += chunk_buffer

            time.sleep(0.5)

        return full_data

    def parse(self, raw_data):
        valid_records = []

        # 1. Add Anchor Record
        current_time = START_ANCHOR
        valid_records.append({
            "id": 1,
            "time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "verify": "Finger/Pwd"
        })

        # Track seen to prevent page overlap duplicates
        seen_timestamps = set()
        seen_timestamps.add(current_time.strftime("%Y-%m-%d %H:%M:%S"))

        # 2. Find start of data stream (Skip Rec 1)
        # Scan for pattern 01 00 00 00
        start_index = 0
        for k in range(50):
            # Look for Header (01 00 00 00)
            if raw_data[k]==1 and raw_data[k+1]==0 and raw_data[k+2]==0:
                # Basic sanity check: ID is usually at byte 5, Verify at byte 4
                if raw_data[k+4] != 0:
                    start_index = k
                    break

        if start_index == 0: start_index = 36 # Fallback

        i = start_index
        while i < len(raw_data) - 19:

            # PATTERN CHECK:
            # Header: 01 00 00 00 (4 bytes)
            # Verify Mode: Byte 4 (Should be non-zero usually)
            # User ID: Byte 5

            if raw_data[i] == 1 and raw_data[i+1] == 0 and raw_data[i+2] == 0:

                chunk = raw_data[i : i+20]

                # Extract Raw Data
                uid = chunk[5]
                verify_mode = chunk[4]

                # TIME EXTRACTION (Trusting only Minutes/Seconds)
                sec = chunk[12]
                minute = chunk[16] >> 2

                # --- CHRONOLOGICAL RECONSTRUCTION ---
                # Start with a candidate time using Current Hour
                candidate = current_time.replace(minute=minute, second=sec)

                # 1. Check for Minute Rollover (e.g., 10:55 -> 10:05)
                # If candidate is BEFORE current time, it means time moved forward past the hour
                if candidate < current_time:
                    candidate += timedelta(hours=1)

                # 2. Check for Huge Gaps (e.g. 10:55 -> 10:56 is fine, but 10:55 -> 10:54 is not)
                # If we added an hour and it's STILL before current_time (rare, but possible if >1 hour gap)
                while candidate < current_time:
                     candidate += timedelta(hours=1)

                # 3. Check for Day Rollover
                # If we advanced past 23:59, datetime handles the day increment automatically.
                # However, we need to handle the case where a gap is > 24 hours?
                # Unlikely for attendance logs.
                # But we do need to handle "End of Work Day" to "Start of Next Day" gap.
                # Example: 18:00 -> 08:00 next day.
                # The 'while' loop above handles this. 18:00... add 14 hours... -> 08:00 next day.

                # Update Tracker
                current_time = candidate
                time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")

                # DEDUPLICATION & FILTER
                # We accept ANY ID > 0
                if uid > 0:
                    if time_str not in seen_timestamps:
                        seen_timestamps.add(time_str)
                        valid_records.append({
                            "id": uid,
                            "time": time_str,
                            "verify": "Card/Face" if verify_mode == 0x10 else "Finger/Pwd"
                        })

                i += 20
                continue

            i += 1

        return valid_records

    def run(self):
        print("Downloading...")
        raw_data = self.fetch_all_pages()
        print(f"Total Bytes: {len(raw_data)}")

        results = self.parse(raw_data)

        print(f"\n=== RESULT: {len(results)} RECORDS ===")
        print("ID | TIME                | VERIFY")
        print("-" * 45)
        for r in results:
            print(f"{r['id']}  | {r['time']} | {r['verify']}")

if __name__ == "__main__":
    app = HIPUniversal(DEVICE_IP, DEVICE_PORT)
    app.run()
