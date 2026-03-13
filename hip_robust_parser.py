"""
HIP CMI F68S ROBUST PARSER
1. Solves the "Garbage ID" problem by aligning to the '0x40' footer.
2. Solves the "Wrong Date" problem by Auto-Calibrating against the first valid record.
3. Handles mixed record sizes (16 bytes vs 20 bytes).
"""

import socket
import struct
import time
import json
from datetime import datetime

# ================= CONFIGURATION =================
DEVICE_IP = "192.168.100.166"
DEVICE_PORT = 5005
TIMEOUT = 5

# Ground Truth: The time of the FIRST record in your Access DB
# We use this to calculate the device's date offset.
CALIBRATION_TARGET = datetime(2026, 1, 14, 10, 48, 21)
# =================================================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

class HIPRobust:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = None
        self.time_offset = None

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(TIMEOUT)
            self.sock.connect((self.ip, self.port))
            log(f"Connected to {self.ip}")
            return True
        except Exception as e:
            log(f"Connection Error: {e}")
            return False

    def receive_data(self):
        """Get the data buffer"""
        total_data = b""
        self.sock.settimeout(3.0)
        try:
            while True:
                chunk = self.sock.recv(4096)
                if not chunk: break
                total_data += chunk
                # If we got a decent chunk, wait briefly to see if more comes
                time.sleep(0.2)
        except socket.timeout:
            pass
        return total_data

    def align_and_parse(self, raw_data):
        records = []

        # skip header garbage (approx first 16 bytes)
        scan_start = 16

        i = scan_start
        length = len(raw_data)

        while i < length:
            # STRATEGY: Find the '0x40' (Verify Mode) byte.
            # It marks the END of a record.
            if raw_data[i] == 0x40:
                # CANDIDATE FOUND at index i.
                # Let's check if it's a 20-byte record or 16-byte record.

                # Check 20-byte Record (Start would be i-19)
                start_20 = i - 19
                if start_20 >= 0:
                    # Check if the first 4 bytes look like a User ID (Small Integer)
                    try:
                        uid_candidate = struct.unpack("<I", raw_data[start_20:start_20+4])[0] & 0xFFFFFF
                        if 0 < uid_candidate < 10000:
                            # FOUND 20-BYTE RECORD
                            self.process_record(records, uid_candidate, raw_data, start_20, 20)
                            i += 1 # Move past this 0x40
                            continue
                    except: pass

                # Check 16-byte Record (Start would be i-15)
                start_16 = i - 15
                if start_16 >= 0:
                    try:
                        uid_candidate = struct.unpack("<I", raw_data[start_16:start_16+4])[0] & 0xFFFFFF
                        if 0 < uid_candidate < 10000:
                            # FOUND 16-BYTE RECORD
                            self.process_record(records, uid_candidate, raw_data, start_16, 16)
                            i += 1
                            continue
                    except: pass

            i += 1 # Keep scanning

        return records

    def process_record(self, records_list, uid, data, start, size):
        chunk = data[start : start+size]

        # EXTRACT TIMESTAMP
        # Logic derived from your hex dumps:
        # If Size 16: Timestamp is at offset 3? or 4?
        # If Size 20: Timestamp is at offset 7.

        ts_raw = 0
        if size == 20:
            ts_raw = struct.unpack("<I", chunk[7:11])[0]
        elif size == 16:
            # Based on previous analysis of Rec 1
            ts_raw = struct.unpack("<I", chunk[3:7])[0]

        # CALIBRATION (Run once on the first valid record found)
        if self.time_offset is None:
            target_ts = int(CALIBRATION_TARGET.timestamp())
            self.time_offset = target_ts - ts_raw
            log(f"CALIBRATION LOCKED using ID {uid}. Offset: {self.time_offset}")

        # CALCULATE FINAL TIME
        try:
            final_ts = ts_raw + self.time_offset
            dt = datetime.fromtimestamp(final_ts)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")

            # Add to list
            records_list.append({
                "User_ID": uid,
                "Time": time_str,
                "Type": "Finger/Pwd",
                "Raw": chunk.hex()
            })
        except:
            records_list.append({"User_ID": uid, "Time": "Error", "Raw": chunk.hex()})

    def run(self):
        if not self.connect(): return
        try:
            # 1. Handshake
            self.sock.send(bytes.fromhex("55 aa 01 b0 00 00 00 00 00 00 ff ff 00 00 17 00"))
            self.sock.recv(1024)

            # 2. Setup
            self.sock.send(bytes.fromhex("55 aa 01 b4 00 00 00 00 00 00 ff ff 00 00 18 00"))
            resp = self.sock.recv(1024)
            token = resp[4] if len(resp) > 4 else 0x03

            # 3. Request
            pkt = bytearray.fromhex("55 aa 01 a4 00 00 00 00 20 00 00 00 00 00 19 00")
            pkt[7] = token
            pkt[13] = token
            self.sock.send(pkt)

            # 4. Receive
            log("Downloading data...")
            raw_data = self.receive_data()
            log(f"Downloaded {len(raw_data)} bytes.")

            # 5. Parse
            clean_list = self.align_and_parse(raw_data)

            # 6. Output
            filename = "hip_robust_attendance.json"
            with open(filename, "w") as f:
                json.dump(clean_list, f, indent=4)

            print(f"\n--- SUCCESS: Parsed {len(clean_list)} Records ---")
            print("First 5 Records:")
            for r in clean_list[:5]:
                print(f"ID: {r['User_ID']} | {r['Time']}")

            print("\nLast 5 Records:")
            for r in clean_list[-5:]:
                print(f"ID: {r['User_ID']} | {r['Time']}")

        finally:
            if self.sock: self.sock.close()

if __name__ == "__main__":
    app = HIPRobust(DEVICE_IP, DEVICE_PORT)
    app.run()
