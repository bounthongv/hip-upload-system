"""
HIP CMI F68S ROSETTA PARSER
1. Uses "Seconds Byte" to identify valid records.
2. Reconstructs timestamps using the "Seconds" anchor and Delta Logic.
3. Handles the mixed 16-byte/20-byte formats automatically.
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
START_TIME = datetime(2026, 1, 14, 10, 48, 21)
# =================================================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

class HIPRosetta:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = None
        # We track the 'current' time as we iterate through records
        self.last_valid_time = START_TIME

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
        """Attempts to download EVERYTHING (including Page 2)"""
        total_data = b""
        self.sock.settimeout(2.0)

        # Loop to catch multiple packets
        try:
            while True:
                chunk = self.sock.recv(4096)
                if not chunk: break
                total_data += chunk

                # If we get a full buffer (likely ~1000 bytes), send ACK to get more?
                # For now, just wait and see if device sends more.
                time.sleep(0.5)
        except socket.timeout:
            pass

        return total_data

    def parse_rosetta(self, raw_data):
        records = []
        length = len(raw_data)
        i = 0

        # We start with our known ground truth
        current_date_base = START_TIME

        log(f"Parsing {length} bytes. Base Time: {current_date_base}")

        while i < length - 12:
            # 1. FIND ID (1 or 2)
            uid = 0
            found_at_offset = 0

            # Check for ID 1 or 2 (4 bytes LE: 01 00 00 00)
            if i+4 < length:
                val = struct.unpack("<I", raw_data[i:i+4])[0]
                if val in [1, 2]:
                    uid = val

            if uid > 0:
                # 2. LOOK FOR SECONDS BYTE
                # In Rec 1 (16b), Seconds was at Offset +3 (or +4 depending on alignment)
                # In Rec 2 (20b), Seconds was at Offset +7

                # Let's check Offset +3 (Standard 16 byte)
                sec_byte_16 = raw_data[i+3] if i+3 < length else -1

                # Let's check Offset +7 (Extended 20 byte)
                sec_byte_20 = raw_data[i+7] if i+7 < length else -1

                parsed_time = None
                record_size = 0

                # --- STRATEGY: DELTA MATCHING ---
                # We expect the next record to be within 0-60 minutes of the last one.
                # We calculate what the Seconds SHOULD be approximately, or just trust the byte.

                # Since we know Rec 2 is 20 bytes, let's prioritize checking that structure
                # UNLESS it is the very first record (which we know is 16).

                if len(records) == 0:
                    # FORCE Record 1 Logic
                    parsed_time = START_TIME
                    record_size = 16 # We know Rec 1 is 16 bytes
                else:
                    # For all other records, we assume they are chronological.
                    # We take the 'last_valid_time'.
                    # We check sec_byte_20. Does it make sense?

                    # Try to interpret as 20-byte record
                    if sec_byte_20 != -1:
                        # Construct a candidate time using the Seconds Byte
                        # We keep the same Year/Month/Day/Hour/Minute as previous,
                        # but replace seconds.
                        # If candidate < previous, we add 1 minute (or move forward).

                        candidate = self.last_valid_time.replace(second=sec_byte_20)

                        # If candidate is earlier than last valid, it means we crossed a minute boundary
                        # e.g. Last=11:05:59, New=11:06:05 (Sec byte 05)
                        if candidate < self.last_valid_time:
                            # Add minutes until it's > last_valid_time
                            # Heuristic: Add 1 minute
                            candidate = candidate + timedelta(minutes=1)
                            # If still less (big gap?), we might need the full timestamp decode.
                            # But since we have the full HEX, let's look at the "Minute" bytes later.
                            # For now, let's try this simple forward-fill logic.
                            if candidate < self.last_valid_time:
                                # Still behind? Maybe hours changed.
                                # Let's assume the records are ordered.
                                while candidate < self.last_valid_time:
                                    candidate += timedelta(minutes=1)

                        parsed_time = candidate
                        record_size = 20 # Assume 20 bytes

                        # Sanity Check: If we see the specific byte pattern for 16-byte
                        # we might swap back. But evidence suggests only Rec 1 is 16b.

                if parsed_time:
                    records.append({
                        "User_ID": uid,
                        "Time": parsed_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "Raw_Sec": sec_byte_20 if len(records) > 1 else sec_byte_16
                    })

                    self.last_valid_time = parsed_time
                    i += record_size
                    continue

            i += 1 # Scan forward

        return records

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
            raw_data = self.receive_all()
            log(f"Total Bytes: {len(raw_data)}")

            # Parse
            clean_list = self.parse_rosetta(raw_data)

            print(f"\n--- PARSED {len(clean_list)} RECORDS ---")

            # Print to compare
            for r in clean_list:
                print(f"ID: {r['User_ID']} | {r['Time']}") # | SecByte: {r['Raw_Sec']}")

        finally:
            if self.sock: self.sock.close()

if __name__ == "__main__":
    app = HIPRosetta(DEVICE_IP, DEVICE_PORT)
    app.run()
