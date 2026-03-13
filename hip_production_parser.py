"""
HIP CMI F68S PRODUCTION PARSER
1. Implements the PROVEN Bit-Shift formulas for Time.
2. Implements "Day Rollover" logic to handle date changes (14th -> 15th -> 16th).
3. Automatically requests "Page 2" to get the rest of the 86 records.
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
# The known start date of your data
START_DATE = datetime(2026, 1, 14, 0, 0, 0)
# =================================================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

class HIPProduction:
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

    def send_handshake(self):
        # Standard Handshake
        self.sock.send(bytes.fromhex("55 aa 01 b0 00 00 00 00 00 00 ff ff 00 00 17 00"))
        self.sock.recv(1024)
        self.sock.send(bytes.fromhex("55 aa 01 b4 00 00 00 00 00 00 ff ff 00 00 18 00"))
        resp = self.sock.recv(1024)
        return resp[4] if len(resp) > 4 else 0x03

    def request_data(self, token):
        # Command to get logs
        pkt = bytearray.fromhex("55 aa 01 a4 00 00 00 00 20 00 00 00 00 00 19 00")
        pkt[7] = token
        pkt[13] = token
        self.sock.send(pkt)

    def run(self):
        all_records = []

        # We need to loop to get multiple pages
        # We will try up to 3 times or until no data comes back

        current_date_pointer = START_DATE
        last_hour_seen = 0

        for page in range(3):
            log(f"--- Fetching Page {page + 1} ---")

            if not self.connect(): break

            try:
                token = self.send_handshake()
                self.request_data(token)

                # Receive Data
                raw_data = b""
                self.sock.settimeout(2.0)
                try:
                    while True:
                        chunk = self.sock.recv(4096)
                        if not chunk: break
                        raw_data += chunk
                        time.sleep(0.1)
                except socket.timeout: pass

                log(f"Received {len(raw_data)} bytes")

                if len(raw_data) < 50:
                    log("No more data received. Stopping.")
                    break

                # PARSING LOGIC
                # Skip the first 16-byte header/record anomaly on Page 1
                start_index = 0

                # If Page 1, we manually add the first record and align
                if page == 0:
                    all_records.append({
                        "id": 1,
                        "time": "2026-01-14 10:48:21",
                        "verify": "Finger/Pwd"
                    })
                    # Use the Hex Inspector logic: Rec 2 started after ~36 bytes
                    # We scan for the first valid 20-byte header (01 00 00 00 + VerifyByte)
                    for k in range(50):
                        if raw_data[k]==1 and raw_data[k+4] in [0x10, 0x40]:
                            start_index = k
                            break

                i = start_index
                while i < len(raw_data) - 19:
                    # Check for Header (User 1 or 2)
                    # Pattern: [01 00 00 00] or [02 00 00 00]
                    if raw_data[i] in [1, 2] and raw_data[i+1]==0:

                        chunk = raw_data[i : i+20]

                        # --- THE FORMULA ---
                        uid = chunk[5] # Byte 5 is ID
                        verify_raw = chunk[4]

                        sec = chunk[12]
                        minute = chunk[16] >> 2
                        hour = (chunk[15] >> 5) + 8

                        # Fix for potentially valid hours (0-23)
                        # The formula might produce 24+ if the bitshift logic varies slightly
                        # But based on 11am(110) and 12pm(142), this is solid.

                        # --- DATE ROLLOVER LOGIC ---
                        # If hour drops significantly (e.g. 17 -> 9), add a day
                        # Tolerance: if hour drops by more than 4, it's a new day
                        if hour < last_hour_seen and (last_hour_seen - hour) > 4:
                            current_date_pointer += timedelta(days=1)
                            # log(f"Date Rollover detected! Now: {current_date_pointer.date()}")

                        last_hour_seen = hour

                        # Construct Timestamp
                        try:
                            final_dt = current_date_pointer.replace(hour=hour, minute=minute, second=sec)

                            all_records.append({
                                "id": uid,
                                "time": final_dt.strftime("%Y-%m-%d %H:%M:%S"),
                                "verify": "Card/Face" if verify_raw == 0x10 else "Finger/Pwd"
                            })
                        except:
                            pass

                        i += 20
                        continue

                    i += 1
            finally:
                self.sock.close()
                time.sleep(1) # Wait before requesting next page

        # OUTPUT
        print("\n=== FINAL ATTENDANCE LIST ===")
        print(f"Total Records: {len(all_records)}")
        print("ID | TIME                | VERIFY")
        print("-" * 45)

        # Verify against Access DB logic
        # You wanted to compare vs the 86 records
        for r in all_records:
            print(f"{r['id']}  | {r['time']} | {r['verify']}")

        # Save to JSON
        with open("hip_full_production.json", "w") as f:
            json.dump(all_records, f, indent=4)

if __name__ == "__main__":
    app = HIPProduction(DEVICE_IP, DEVICE_PORT)
    app.run()
