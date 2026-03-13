"""
HIP CMI F68S Smart Parser
1. Uses 'Fuzzy Logic' to find records even if they have different lengths/padding.
2. Auto-Calibrates time.
3. Fixes the loop to try and catch more data.
"""

import socket
import struct
import time
import json
from datetime import datetime

# ================= CONFIGURATION =================
DEVICE_IP = "192.168.100.166"
DEVICE_PORT = 5005
TIMEOUT = 10
CALIBRATION_TARGET = datetime(2026, 1, 14, 10, 48, 21) # The first record time
# =================================================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

class HIPSmartPuller:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = None
        self.time_offset = 0

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

    def receive_all(self):
        """improved receive loop with pauses"""
        total_data = b""
        self.sock.settimeout(2.0)

        # Try to read 5 chunks
        for i in range(5):
            try:
                chunk = self.sock.recv(4096)
                if chunk:
                    total_data += chunk
                    # log(f"Chunk {i+1}: Received {len(chunk)} bytes")
                else:
                    break
            except socket.timeout:
                break
            time.sleep(0.5) # Give device time to push next packet

        return total_data

    def smart_parse(self, raw_data):
        records = []

        # 1. Skip Header (Approx 16 bytes, but let's just start scanning)
        # We start calibration using the KNOWN First Record timestamp logic from previous run
        # Rec 1 Raw was: 1309800981 (from your log)
        # Target: 1768362501 (2026-01-14...)
        # Offset was: 458561520

        # We will calculate offset dynamically again to be safe
        offset_calculated = False

        # Scan through the byte array
        i = 12 # Skip initial header
        length = len(raw_data)

        while i < length - 10:
            # SEARCH FOR ID PATTERN: Little Endian 1 or 2
            # 01 00 00 or 02 00 00
            uid = 0

            # Check for ID 1
            if raw_data[i] == 0x01 and raw_data[i+1] == 0x00 and raw_data[i+2] == 0x00:
                uid = 1
            # Check for ID 2
            elif raw_data[i] == 0x02 and raw_data[i+1] == 0x00 and raw_data[i+2] == 0x00:
                uid = 2

            if uid > 0:
                # We found a potential ID at index 'i'
                # The timestamp is usually within the next 4-12 bytes.
                # Let's brute force scan the next 16 bytes for a valid date.

                valid_date_found = False

                for j in range(3, 16): # Check offsets 3 to 16 from ID
                    if i + j + 4 > length: break

                    # Grab 4 bytes
                    ts_bytes = raw_data[i+j : i+j+4]
                    ts_raw = struct.unpack("<I", ts_bytes)[0]

                    # Try to calibrate if first record
                    if not offset_calculated:
                        # Force calibration against the first record found
                        target_ts = int(CALIBRATION_TARGET.timestamp())
                        self.time_offset = target_ts - ts_raw
                        offset_calculated = True
                        log(f"CALIBRATION LOCKED: Offset {self.time_offset}")

                    # Calculate Date
                    check_ts = ts_raw + self.time_offset

                    try:
                        dt = datetime.fromtimestamp(check_ts)
                        # VALIDATION: Is the year reasonable? (2025-2027)
                        if 2025 <= dt.year <= 2027:
                            records.append({
                                "User_ID": uid,
                                "Time": dt.strftime("%Y-%m-%d %H:%M:%S"),
                                "Raw_Index": i
                            })
                            valid_date_found = True

                            # Move pointer forward to avoid re-reading this record
                            # Jump at least 16 bytes
                            i += 16
                            break
                    except:
                        pass

                if not valid_date_found:
                    i += 1 # No valid date found near this ID, keep scanning
            else:
                i += 1 # Not an ID, keep scanning

        return records

    def run(self):
        if not self.connect(): return

        try:
            # Handshake & Setup
            self.sock.send(bytes.fromhex("55 aa 01 b0 00 00 00 00 00 00 ff ff 00 00 17 00"))
            self.sock.recv(1024)
            self.sock.send(bytes.fromhex("55 aa 01 b4 00 00 00 00 00 00 ff ff 00 00 18 00"))
            resp = self.sock.recv(1024)
            token = resp[4] if len(resp) > 4 else 0x03

            # Request
            pkt_req = bytearray.fromhex("55 aa 01 a4 00 00 00 00 20 00 00 00 00 00 19 00")
            pkt_req[7] = token
            pkt_req[13] = token
            self.sock.send(pkt_req)

            # Receive
            log("Receiving data...")
            raw_data = self.receive_all()
            log(f"Total binary: {len(raw_data)} bytes")

            # Parse
            clean_records = self.smart_parse(raw_data)

            # Save
            filename = f"hip_attendance_final_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
            with open(filename, "w") as f:
                json.dump(clean_records, f, indent=4)

            log(f"Parsed {len(clean_records)} valid records.")
            print("\n--- RESULTS SAMPLE ---")
            for r in clean_records[:10]:
                print(f"ID: {r['User_ID']} | {r['Time']}")

        except Exception as e:
            log(f"Error: {e}")
        finally:
            if self.sock: self.sock.close()

if __name__ == "__main__":
    puller = HIPSmartPuller(DEVICE_IP, DEVICE_PORT)
    puller.run()
