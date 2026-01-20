"""
HIP CMI F68S Attendance Log Puller - WORKING VERSION
"""
import socket
import time
import struct
import sys
from datetime import datetime

def log_msg(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def hex_dump(data, label=""):
    if not data:
        print(f"{label}: (empty)")
        return
    hex_str = ' '.join(f'{b:02x}' for b in data[:64])
    if len(data) > 64:
        hex_str += f" ... ({len(data)-64} more bytes)"
    print(f"{label}: {hex_str}")

class HIPDevice:
    def __init__(self, ip, port=5005):
        self.ip = ip
        self.port = port
        self.sock = None

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((self.ip, self.port))
            log_msg(f"Connected to {self.ip}:{self.port}")
            return True
        except Exception as e:
            log_msg(f"Connection failed: {e}")
            return False

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def send_packet(self, data):
        try:
            hex_dump(data, "Sending")
            self.sock.send(data)
            return True
        except Exception as e:
            log_msg(f"Send failed: {e}")
            return False

    def receive_packet(self, timeout=15):
        old_timeout = self.sock.gettimeout()
        self.sock.settimeout(timeout)
        try:
            data = self.sock.recv(65535)
            if data:
                hex_dump(data, f"Received ({len(data)} bytes)")
            return data
        except socket.timeout:
            log_msg("Receive timeout")
            return None
        except Exception as e:
            log_msg(f"Receive error: {e}")
            return None
        finally:
            self.sock.settimeout(old_timeout)

    def pull_attendance_logs(self):
        """Pull attendance logs using discovered protocol"""

        if not self.connect():
            return None

        try:
            log_msg("=== Starting HIP Protocol ===")

            # ----- PHASE 1: Handshake -----
            log_msg("1. Sending handshake...")
            pkt8 = bytes.fromhex("55 aa 01 b0 00 00 00 00 00 00 ff ff 00 00 17 00")
            if not self.send_packet(pkt8):
                return None

            resp1 = self.receive_packet(timeout=5)
            if not resp1:
                log_msg("ERROR: No handshake response")
                return None

            time.sleep(0.1)

            # ----- PHASE 2: Setup -----
            log_msg("2. Sending setup command...")
            pkt10 = bytes.fromhex("55 aa 01 b4 00 00 00 00 00 00 ff ff 00 00 18 00")
            if not self.send_packet(pkt10):
                return None

            resp2 = self.receive_packet(timeout=5)
            if not resp2:
                log_msg("ERROR: No setup response")
                return None

            # Extract token from Packet 11 response
            # Response format: aa 55 01 00 TOKEN 00 00 00 18 00
            token = 0x03  # Default
            if len(resp2) >= 5:
                token = resp2[4]
                log_msg(f"Extracted token from device: 0x{token:02x}")

            time.sleep(0.2)

            # ----- PHASE 3: Request Attendance Data -----
            log_msg("3. Requesting attendance logs...")

            # Build Packet 12 dynamically using the token
            # Format: 55 aa 01 a4 00 00 00 TOKEN 20 00 00 00 00 TOKEN 19 00
            pkt12 = bytes([
                0x55, 0xaa, 0x01, 0xa4,       # Header
                0x00, 0x00, 0x00, token,      # Token in position 4-7
                0x20, 0x00, 0x00, 0x00,       # Fixed 0x20
                0x00, token,                  # Token again at the end
                0x19, 0x00                    # Footer
            ])

            log_msg(f"Using token 0x{token:02x} in Packet 12")
            if not self.send_packet(pkt12):
                return None

            # ----- PHASE 4: Receive Attendance Data -----
            log_msg("4. Receiving attendance data...")
            attendance_data = self.receive_packet(timeout=30)

            if attendance_data and len(attendance_data) > 100:
                log_msg(f"✓ SUCCESS! Received {len(attendance_data)} bytes of attendance data")
                return attendance_data
            else:
                log_msg("✗ FAILED: No data received or data too small")
                return None

        except Exception as e:
            log_msg(f"Error during communication: {e}")
            return None
        finally:
            self.disconnect()

    def parse_attendance_data(self, data):
        """Parse the attendance data structure"""

        log_msg("\n=== Parsing Attendance Data ===")
        log_msg(f"Total data size: {len(data)} bytes")

        # Save raw data
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        raw_filename = f"hip_attendance_raw_{timestamp}.bin"
        with open(raw_filename, 'wb') as f:
            f.write(data)
        log_msg(f"Raw data saved to: {raw_filename}")

        # The data appears to start with aa 55 01 01 00 00 00 00 19 00
        # This is an acknowledgment header, then the actual data starts

        # Skip the 10-byte header if present
        if data.startswith(bytes.fromhex("aa550101000000001900")):
            log_msg("Found acknowledgment header, skipping 10 bytes")
            actual_data = data[10:]
        else:
            actual_data = data

        log_msg(f"Actual attendance data: {len(actual_data)} bytes")

        # Try to parse records
        # Common HIP record sizes: 40 bytes is common
        record_size = 40

        if len(actual_data) % record_size == 0:
            num_records = len(actual_data) // record_size
            log_msg(f"Found {num_records} attendance records ({record_size} bytes each)")

            # Parse each record
            log_msg("\n=== Attendance Records ===")
            for i in range(min(10, num_records)):  # Show first 10 records
                start = i * record_size
                record = actual_data[start:start + record_size]
                self.parse_single_record(i+1, record)

            if num_records > 10:
                log_msg(f"... and {num_records - 10} more records")
        else:
            log_msg(f"Could not determine record structure")
            log_msg(f"First 100 bytes of actual data:")
            hex_str = ' '.join(f'{b:02x}' for b in actual_data[:100])
            print(hex_str)

    def parse_single_record(self, record_num, record):
        """Parse a single attendance record"""
        if len(record) < 40:
            return

        # Common HIP record structure (guess based on common patterns):
        # Bytes 0-3: User ID
        # Bytes 4-7: Timestamp (Unix timestamp)
        # Bytes 8-11: Verification mode
        # Bytes 12-15: Work code
        # etc...

        user_id = int.from_bytes(record[0:4], byteorder='little', signed=False)
        timestamp_val = int.from_bytes(record[4:8], byteorder='little', signed=False)

        # Convert Unix timestamp to readable date
        try:
            from datetime import datetime
            dt = datetime.fromtimestamp(timestamp_val)
            time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            time_str = f"Invalid timestamp: {timestamp_val}"

        # Status/verification mode
        status = record[8] if len(record) > 8 else 0

        # Common status values:
        status_map = {
            0: "Check-in",
            1: "Check-out",
            5: "OT Start",
            6: "OT End",
            0x15: "Fingerprint",
            0x41: "Password",
            0x42: "Card"
        }

        status_desc = status_map.get(status, f"Unknown ({status:02x})")

        log_msg(f"Record {record_num:3d}: UserID={user_id:6d}, Time={time_str}, Status={status_desc}")

def main():
    import sys

    if len(sys.argv) > 1:
        device_ip = sys.argv[1]
    else:
        device_ip = "192.168.100.166"
        log_msg(f"No IP provided, using default: {device_ip}")

    log_msg(f"HIP CMI F68S Attendance Log Puller")
    log_msg(f"Target device: {device_ip}:5005")
    log_msg("=" * 50)

    device = HIPDevice(device_ip)

    # Pull the data
    data = device.pull_attendance_logs()

    if data:
        log_msg("\n" + "=" * 50)
        log_msg("ATTENDANCE DATA RETRIEVED SUCCESSFULLY!")
        log_msg("=" * 50)

        # Parse and display the data
        device.parse_attendance_data(data)

        # Also save as text file
        txt_filename = f"hip_attendance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(txt_filename, 'w', encoding='utf-8') as f:
            f.write(f"HIP CMI F68S Attendance Log\n")
            f.write(f"Downloaded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Device IP: {device_ip}\n")
            f.write(f"Data size: {len(data)} bytes\n")
            f.write("=" * 50 + "\n")
            f.write(f"Raw hex (first 500 bytes):\n")
            hex_str = ' '.join(f'{b:02x}' for b in data[:500])
            f.write(hex_str + "\n")

        log_msg(f"\nSummary saved to: {txt_filename}")
        log_msg("\n✓ COMPLETE: Attendance logs downloaded successfully!")

    else:
        log_msg("\n✗ FAILED: Could not retrieve attendance logs")

    log_msg("\nDone.")

if __name__ == "__main__":
    main()
