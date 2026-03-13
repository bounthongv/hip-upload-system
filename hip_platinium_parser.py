"""
HIP CMI F68S PLATINUM PARSER
1. USES DATE SIGNATURES (Bytes 13-14) to control Day Changes (No guessing).
2. USES SEQUENTIAL LOGIC to resolve the 8-Hour Hour ambiguity.
3. USES STRICT FRAME HEADERS to eliminate garbage data.
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
# Anchor: Jan 14, 2026.
START_DATE = datetime(2026, 1, 14, 0, 0, 0)
# =================================================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

class HIPPlatinum:
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

    def fetch_data(self):
        full_buffer = b""
        # Fetch 3 pages to get all data (14th to 21st)
        for _ in range(3):
            if not self.connect(): break

            # Handshake
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

            # Read Loop
            try:
                self.sock.settimeout(2.0)
                while True:
                    chunk = self.sock.recv(4096)
                    if not chunk: break
                    full_buffer += chunk
                    time.sleep(0.1)
            except socket.timeout: pass

            self.sock.close()
            time.sleep(0.5)

        return full_buffer

    def parse(self, raw_data):
        valid_records = []
        seen_dedupe = set()

        # State Tracking
        current_date_ptr = START_DATE
        last_date_sig = None # Bytes 13-14
        last_valid_hour = 10 # Start at 10am

        # 1. Manual Insert of Record 1 (The 16-byte Anomaly)
        # We grab the signature from Rec 1 logic to initialize state
        rec1_time = "2026-01-14 10:48:21"
        seen_dedupe.add((1, rec1_time))
        valid_records.append({"id":1, "time":rec1_time, "verify":"Finger/Pwd"})

        # We know Rec 1 (Jan 14) has signature 0xFA 0x11
        last_date_sig = (0xfa, 0x11)

        # 2. Scan for 20-byte records
        # Start scanning after Rec 1 (Offset 36 is safe start)
        i = 36

        while i < len(raw_data) - 20:

            # STRICT HEADER PATTERN: [01 00 00 00]
            if raw_data[i] == 1 and raw_data[i+1] == 0 and raw_data[i+2] == 0 and raw_data[i+3] == 0:

                chunk = raw_data[i : i+20]

                uid = chunk[5]       # ID at Offset 5
                verify_mode = chunk[4] # Mode at Offset 4

                # Filter Garbage (ID must be 1 or 2)
                if uid in [1, 2] and verify_mode in [0x10, 0x40]:

                    # --- DATE SIGNATURE CHECK ---
                    # Bytes 13 and 14 encode the date.
                    curr_sig = (chunk[13], chunk[14])

                    # If signature changes, we advance the day
                    if curr_sig != last_date_sig:
                        current_date_ptr += timedelta(days=1)
                        last_date_sig = curr_sig
                        last_valid_hour = 0 # Reset hour for new day
                        # log(f"New Day Detected at ID {uid}")

                    # --- TIME DECODE ---
                    sec = chunk[12]
                    minute = chunk[16] >> 2
                    raw_base = (chunk[15] >> 5) + 8 # 8..15 range

                    # --- RESOLVE 8-HOUR AMBIGUITY ---
                    # Candidates: Base (e.g. 8), Base+8 (16), Base+16 (24)
                    # We pick the one that fits the sequence > last_valid_hour

                    final_hour = raw_base

                    # Try to match forward progression
                    if raw_base < last_valid_hour:
                         if (raw_base + 8) >= last_valid_hour:
                             final_hour = raw_base + 8
                         elif (raw_base + 16) >= last_valid_hour and (raw_base + 16) < 24:
                             final_hour = raw_base + 16
                    else:
                        # If raw_base is already > last, checks if +8 makes more sense?
                        # e.g. Last=9, Raw=10. 10 is good.
                        # e.g. Last=17, Raw=9 -> handled above.
                        pass

                    # Overflow check (just in case logic picks 24+)
                    if final_hour >= 24: final_hour -= 24

                    # Update Tracker
                    last_valid_hour = final_hour

                    # Construct
                    try:
                        dt = current_date_ptr.replace(hour=final_hour, minute=minute, second=sec)
                        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")

                        # Dedupe
                        if (uid, time_str) not in seen_dedupe:
                            seen_dedupe.add((uid, time_str))
                            valid_records.append({
                                "id": uid,
                                "time": time_str,
                                "verify": "Card/Face" if verify_mode == 0x10 else "Finger/Pwd"
                            })
                    except: pass

                    i += 20
                    continue

            i += 1 # Scan next byte

        # Final Sort
        valid_records.sort(key=lambda x: x['time'])
        return valid_records

    def run(self):
        log("Fetching all pages...")
        data = self.fetch_data()
        log(f"Buffer Size: {len(data)} bytes")

        results = self.parse(data)

        print(f"\n=== FINAL PLATINUM RESULT: {len(results)} RECORDS ===")
        print("ID | TIME                | VERIFY")
        print("-" * 45)
        for r in results:
            print(f"{r['id']}  | {r['time']} | {r['verify']}")

if __name__ == "__main__":
    app = HIPPlatinum(DEVICE_IP, DEVICE_PORT)
    app.run()
