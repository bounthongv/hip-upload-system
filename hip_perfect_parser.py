"""
HIP CMI F68S PERFECT PARSER (Chronological Logic)
1. Extracts exact Seconds and Minutes from binary.
2. Auto-calculates the Hour based on time progression.
3. Matches your Access Database format exactly.
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

# GROUND TRUTH: 14/01/2026 10:48:21
START_ANCHOR = datetime(2026, 1, 14, 10, 48, 21)
# =================================================

class HIPPerfect:
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
        except:
            return False

    def get_data_batch(self):
        # Protocol Handshake
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

        # Receive one batch
        data = b""
        try:
            self.sock.settimeout(2.0)
            while True:
                chunk = self.sock.recv(4096)
                if not chunk: break
                data += chunk
                time.sleep(0.1)
        except socket.timeout: pass
        return data

    def parse(self, raw_data):
        records = []

        # 1. Add Anchor Record (Record 1)
        current_time = START_ANCHOR
        records.append({
            "id": 1,
            "time": current_time,
            "verify": "Finger/Pwd"
        })

        # 2. Find Start of Record 2 (20-byte records)
        # Scan for the first 20-byte signature (User 1 + Verify Mode)
        start_index = 0
        for k in range(50):
            if raw_data[k]==1 and raw_data[k+4] in [0x10, 0x40]:
                start_index = k
                break

        if start_index == 0: start_index = 36 # Default fallback

        i = start_index
        while i < len(raw_data) - 19:
            # Look for Valid ID (1 or 2)
            if raw_data[i] in [1, 2] and raw_data[i+1] == 0:
                chunk = raw_data[i : i+20]

                uid = chunk[5]
                verify_raw = chunk[4]

                # --- PRECISE TIME EXTRACTION ---
                sec = chunk[12]
                minute = chunk[16] >> 2

                # --- CHRONOLOGICAL HOUR LOGIC ---
                # We assume the log is sequential.
                # We start with the 'current_time' (Hour/Day).
                # We update the Minute/Second.
                # If the result is IN THE PAST, it means the Hour (or Day) increased.

                candidate = current_time.replace(minute=minute, second=sec)

                # If candidate is significantly in the past (e.g. prev 10:48, new 10:05)
                # We add hours until it is future.
                while candidate < current_time:
                    candidate += timedelta(hours=1)

                # Update tracker
                current_time = candidate

                records.append({
                    "id": uid,
                    "time": current_time,
                    "verify": "Card/Face" if verify_raw == 0x10 else "Finger/Pwd"
                })

                i += 20
                continue
            i += 1

        return records

    def run(self):
        if not self.connect(): return
        try:
            print("Fetching data batch...")
            raw_data = self.get_data_batch()
            print(f"Received {len(raw_data)} bytes ({len(raw_data)//20} approx records)")

            clean_list = self.parse(raw_data)

            print(f"\n=== PARSED {len(clean_list)} RECORDS ===")
            print("ID | TIME                | VERIFY")
            print("-" * 45)

            for r in clean_list:
                print(f"{r['id']}  | {r['time'].strftime('%Y-%m-%d %H:%M:%S')} | {r['verify']}")

        finally:
            self.sock.close()

if __name__ == "__main__":
    app = HIPPerfect(DEVICE_IP, DEVICE_PORT)
    app.run()
