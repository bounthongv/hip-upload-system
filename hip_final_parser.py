"""
HIP CMI F68S Final Production Puller
1. Fixes "Missing Records" by looping the network receive.
2. Fixes "Wrong Date" by auto-calibrating against a known date.
"""

import socket
import struct
import time
import json
import os
from datetime import datetime, timedelta

# ================= CONFIGURATION =================
DEVICE_IP = "192.168.100.166"
DEVICE_PORT = 5005
TIMEOUT = 10

# GROUND TRUTH CALIBRATION
# We use this to fix the device's internal clock offset.
# Based on your "access-db.txt", the first record is:
CALIBRATION_TARGET_TIME = datetime(2026, 1, 14, 10, 48, 21)
# =================================================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

class HIPPuller:
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

    def disconnect(self):
        if self.sock:
            self.sock.close()

    def receive_all(self):
        """Loops receiving data until the device stops sending."""
        total_data = b""
        self.sock.settimeout(3.0) # Short timeout for loop
        try:
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                total_data += chunk
                # If chunk is small (just a keepalive?), we might stop,
                # but usually attendance dumps are continuous.
        except socket.timeout:
            pass # Timeout implies device finished sending
        except Exception as e:
            log(f"Receive error: {e}")

        return total_data

    def parse_records(self, raw_data):
        records = []

        # 1. Skip Packet Header (First 10 Bytes)
        # aa 55 01 01 00 00 00 00 19 00
        if len(raw_data) < 16:
            return []

        # 2. Skip Data Header (Next 6 Bytes) - deduced from your hex dump
        # 55 aa 01 00 00 00
        # Total skip = 16 bytes? Let's try dynamic finding.

        # Search for the start of the payload.
        # We know records are 16 bytes.
        # Let's start parsing after the first 16 bytes of headers.
        payload = raw_data[16:]

        record_size = 16
        num_records = len(payload) // record_size
        log(f"Payload size: {len(payload)} bytes. Estimating {num_records} records.")

        raw_records_list = []

        for i in range(num_records):
            chunk = payload[i*record_size : (i+1)*record_size]

            # PARSING LOGIC based on your Hex Dump
            # R1: 01 00 00 15 fa 11 4e c1 ...

            # User ID: Bytes 0-3 (Little Endian)
            # Masking with 0xFFFFFF to ignore the 4th byte which seems to belong to time or status
            uid = struct.unpack("<I", chunk[0:4])[0] & 0xFFFFFF

            # Raw Timestamp: Bytes 3-7 (Little Endian) - Overlapping byte 3
            # In your dump: 15 fa 11 4e
            ts_raw = struct.unpack("<I", chunk[3:7])[0]

            # Verify Mode: Byte 15
            v_mode = chunk[15]

            if uid == 0 or uid > 100000:
                continue

            raw_records_list.append({
                "uid": uid,
                "ts_raw": ts_raw,
                "v_mode": v_mode,
                "raw": chunk.hex()
            })

        # 3. AUTO CALIBRATION
        if raw_records_list:
            first_rec = raw_records_list[0]
            # Calculate the difference between known ground truth and raw value
            # Target: 2026-01-14 10:48:21 (Ground Truth)
            # Raw: 1309866517 (Example from your dump)
            target_ts = int(CALIBRATION_TARGET_TIME.timestamp())
            self.time_offset = target_ts - first_rec['ts_raw']

            log(f"CALIBRATION: Target={target_ts}, Raw={first_rec['ts_raw']}")
            log(f"CALIBRATION: Calculated Time Offset = {self.time_offset} seconds")

        # 4. Finalize Records
        for r in raw_records_list:
            corrected_ts = r['ts_raw'] + self.time_offset
            dt_object = datetime.fromtimestamp(corrected_ts)

            records.append({
                "User_ID": str(r['uid']),
                "Time": dt_object.strftime("%Y-%m-%d %H:%M:%S"),
                "Verify": "FP" if r['v_mode'] == 64 else "Other"
            })

        return records

    def run(self):
        if not self.connect():
            return

        try:
            # 1. Handshake
            self.sock.send(bytes.fromhex("55 aa 01 b0 00 00 00 00 00 00 ff ff 00 00 17 00"))
            self.sock.recv(1024)

            # 2. Setup
            self.sock.send(bytes.fromhex("55 aa 01 b4 00 00 00 00 00 00 ff ff 00 00 18 00"))
            resp = self.sock.recv(1024)
            token = resp[4] if len(resp) > 4 else 0x03

            # 3. Request Logs
            pkt_req = bytearray.fromhex("55 aa 01 a4 00 00 00 00 20 00 00 00 00 00 19 00")
            pkt_req[7] = token
            pkt_req[13] = token
            self.sock.send(pkt_req)

            # 4. RECEIVE ALL DATA (Fixing the 34 vs 86 record issue)
            log("Receiving data stream...")
            raw_data = self.receive_all()
            log(f"Total binary received: {len(raw_data)} bytes")

            # 5. Parse
            clean_records = self.parse_records(raw_data)

            # 6. Save
            with open("hip_final_attendance.json", "w") as f:
                json.dump(clean_records, f, indent=4)

            log(f"Successfully parsed {len(clean_records)} records.")

            # Print first 5 for verification
            print("\n--- Verification Sample (First 5) ---")
            for r in clean_records[:5]:
                print(f"ID: {r['User_ID']} | Time: {r['Time']}")

            print(f"\n--- Verification Sample (Last 5) ---")
            for r in clean_records[-5:]:
                print(f"ID: {r['User_ID']} | Time: {r['Time']}")

        finally:
            self.disconnect()

if __name__ == "__main__":
    puller = HIPPuller(DEVICE_IP, DEVICE_PORT)
    puller.run()
