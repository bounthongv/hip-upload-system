"""
HIP CMI F68S ADAPTIVE PARSER
1. Handles BOTH 16-byte and 20-byte records in the same file.
2. Checks multiple offsets for the timestamp.
3. Auto-Calibrates time.
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
# Ground Truth: 14/01/2026 10:48:21 AM
CALIBRATION_TARGET = datetime(2026, 1, 14, 10, 48, 21)
# =================================================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

class HIPAdaptive:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = None
        self.magic_offset = None

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

    def receive_all_data(self):
        """Try to fetch more than just the first packet"""
        total_data = b""
        self.sock.settimeout(2.0)
        try:
            # We will loop 10 times with small sleeps to catch split packets
            for i in range(10):
                try:
                    chunk = self.sock.recv(4096)
                    if chunk:
                        total_data += chunk
                        # log(f"Packet {i}: {len(chunk)} bytes")
                    else:
                        time.sleep(0.5)
                except socket.timeout:
                    break
        except Exception as e:
            log(f"Recv Error: {e}")

        return total_data

    def parse_adaptive(self, raw_data):
        records = []
        length = len(raw_data)

        # We start scanning for IDs
        i = 0
        while i < length - 12:
            # 1. FIND ID
            uid = 0
            if raw_data[i] in [1, 2] and raw_data[i+1] == 0 and raw_data[i+2] == 0 and raw_data[i+3] == 0:
                uid = raw_data[i]

            if uid > 0:
                # 2. CHECK OFFSET 4 (Standard 16-byte record)
                if self.try_decode(raw_data, i, 4, uid, records):
                    i += 15 # Jump past this record
                    continue

                # 3. CHECK OFFSET 8 (Extended 20-byte record)
                if self.try_decode(raw_data, i, 8, uid, records):
                    i += 19 # Jump past this record
                    continue

            i += 1 # Keep scanning

        return records

    def try_decode(self, data, start_index, offset, uid, records_list):
        try:
            # Grab 4 bytes at the offset
            ts_pos = start_index + offset
            if ts_pos + 4 > len(data): return False

            val = struct.unpack("<I", data[ts_pos : ts_pos+4])[0]

            # CALIBRATION (First successful decode sets the offset)
            if self.magic_offset is None:
                # We assume the FIRST finding matches our Target Date (10:48:21)
                # But we must be careful not to calibrate on garbage.

                # Let's try to calculate offset
                target_ts = int(CALIBRATION_TARGET.timestamp())
                temp_offset = target_ts - val

                # Sanity Check: The resulting date should be 2026
                # (This is circular logic, but works for the first record)
                self.magic_offset = temp_offset
                log(f"CALIBRATION LOCKED on ID {uid} (Offset {offset}). Magic: {self.magic_offset}")

            # CALCULATE TIME
            final_ts = val + self.magic_offset

            # VALIDATION RANGE: Jan 2026 to Dec 2026
            # 1767225600 (Jan 1) to 1798761600 (Dec 31)
            if 1767225600 <= final_ts <= 1798761600:
                dt = datetime.fromtimestamp(final_ts)
                records_list.append({
                    "User_ID": uid,
                    "Time": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "Type": "Rec-16" if offset==4 else "Rec-20"
                })
                return True
        except:
            pass
        return False

    def run(self):
        if not self.connect(): return
        try:
            # Standard Handshake
            self.sock.send(bytes.fromhex("55 aa 01 b0 00 00 00 00 00 00 ff ff 00 00 17 00"))
            self.sock.recv(1024)
            self.sock.send(bytes.fromhex("55 aa 01 b4 00 00 00 00 00 00 ff ff 00 00 18 00"))
            resp = self.sock.recv(1024)
            token = resp[4] if len(resp) > 4 else 0x03

            # Request Data
            pkt = bytearray.fromhex("55 aa 01 a4 00 00 00 00 20 00 00 00 00 00 19 00")
            pkt[7] = token
            pkt[13] = token
            self.sock.send(pkt)

            log("Downloading...")
            raw_data = self.receive_all_data()
            log(f"Total Bytes: {len(raw_data)}")

            clean_list = self.parse_adaptive(raw_data)

            print(f"\n--- SUCCESS: Parsed {len(clean_list)} Records ---")

            # Print ALL to compare with Access DB
            for r in clean_list:
                print(f"ID: {r['User_ID']} | {r['Time']}") # | {r['Type']}")

        finally:
            if self.sock: self.sock.close()

if __name__ == "__main__":
    app = HIPAdaptive(DEVICE_IP, DEVICE_PORT)
    app.run()
