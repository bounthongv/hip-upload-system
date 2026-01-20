"""
UDP Listener for HIP Device
Checks if the device sends announcements via UDP before/during TCP connection.
"""
import socket
import sys
from datetime import datetime

def log_msg(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def hex_dump(data):
    if not data: return
    hex_str = ' '.join(f'{b:02x}' for b in data)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
    print(f"  HEX: {hex_str}")
    print(f"  TXT: {ascii_str}")

def start_udp_server(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(('0.0.0.0', port))
        log_msg(f"Listening on UDP port {port}...")
        
        while True:
            data, addr = sock.recvfrom(4096)
            log_msg(f"Received {len(data)} bytes from {addr[0]}:{addr[1]}")
            hex_dump(data)
            
            # Save packet
            with open(f"udp_{port}_{datetime.now().strftime('%H%M%S')}.bin", "wb") as f:
                f.write(data)
                
    except Exception as e:
        log_msg(f"Error: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9090
    start_udp_server(port)
