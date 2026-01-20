"""
TCP Proxy Logger (Man-in-the-Middle)

Captures traffic between HIP Device and HIP Premium Time Software.

Configuration:
1. DEVICE connects to this script on LISTEN_PORT (9090)
2. This script forwards to SOFTWARE on TARGET_PORT (9091)
3. You must change HIP Premium Time software to listen on 9091
"""
import socket
import threading
import time
import sys
import os
from datetime import datetime

# Configuration
LISTEN_HOST = '0.0.0.0'
LISTEN_PORT = 9090        # Device connects here
TARGET_HOST = '127.0.0.1' # Software is running locally
TARGET_PORT = 9091        # Software listens here (CHANGE SOFTWARE SETTING TO THIS)

def log_msg(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def hex_dump(data, prefix=""):
    if not data: return
    hex_str = ' '.join(f'{b:02x}' for b in data)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
    print(f"{prefix}HEX: {hex_str}")
    print(f"{prefix}TXT: {ascii_str}")

def handle_client(client_socket, client_addr):
    log_msg(f"Device connected from {client_addr[0]}:{client_addr[1]}")
    
    # Connect to the real software
    try:
        target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        target_socket.connect((TARGET_HOST, TARGET_PORT))
        log_msg(f"Connected to HIP Software on {TARGET_HOST}:{TARGET_PORT}")
    except Exception as e:
        log_msg(f"ERROR: Could not connect to HIP Software on port {TARGET_PORT}")
        log_msg("Make sure HIP Premium Time is running and listening on port 9091")
        client_socket.close()
        return

    # Start bi-directional forwarding
    
    # Device -> Software
    def forward_device_to_software():
        try:
            while True:
                data = client_socket.recv(4096)
                if not data: break
                
                log_msg(f">>> DEVICE SENT ({len(data)} bytes):")
                hex_dump(data, "    ")
                
                target_socket.send(data)
        except Exception as e:
            pass
        finally:
            client_socket.close()
            target_socket.close()

    # Software -> Device
    def forward_software_to_device():
        try:
            while True:
                data = target_socket.recv(4096)
                if not data: break
                
                log_msg(f"<<< SOFTWARE SENT ({len(data)} bytes):")
                hex_dump(data, "    ")
                
                client_socket.send(data)
        except Exception as e:
            pass
        finally:
            client_socket.close()
            target_socket.close()

    t1 = threading.Thread(target=forward_device_to_software)
    t2 = threading.Thread(target=forward_software_to_device)
    
    t1.daemon = True
    t2.daemon = True
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    log_msg("Connection closed")

def start_proxy():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((LISTEN_HOST, LISTEN_PORT))
        server.listen(5)
        
        log_msg("="*60)
        log_msg(f"HIP PROXY LOGGER STARTED")
        log_msg(f"Listening for Device on: {LISTEN_PORT}")
        log_msg(f"Forwarding to Software on: {TARGET_PORT}")
        log_msg("="*60)
        log_msg("IMPORTANT: Ensure HIP Premium Time is running on port 9091")
        log_msg("Waiting for connection...")
        
        while True:
            client_sock, client_addr = server.accept()
            threading.Thread(target=handle_client, args=(client_sock, client_addr)).start()
            
    except KeyboardInterrupt:
        log_msg("Proxy stopped")
    except Exception as e:
        log_msg(f"Proxy error: {e}")
    finally:
        server.close()

if __name__ == "__main__":
    # Allow command line overrides: python hip_proxy.py [listen_port] [target_port]
    if len(sys.argv) > 1:
        LISTEN_PORT = int(sys.argv[1])
    if len(sys.argv) > 2:
        TARGET_PORT = int(sys.argv[2])
        
    start_proxy()
