"""
Raw TCP Listener - Capture any data the HIP device sends

This listens on a port and logs EVERYTHING that comes in,
regardless of protocol. This will help us understand what
the HIP CMI F68S device actually sends.
"""
import socket
import threading
import time
import sys
from datetime import datetime

def log_msg(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def hex_dump(data):
    """Pretty print hex dump"""
    if not data:
        return
    
    # Hex view
    hex_lines = []
    ascii_lines = []
    
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        hex_lines.append(f"  {i:04x}: {hex_part:<48} {ascii_part}")
    
    for line in hex_lines:
        print(line)

def handle_client(client_socket, client_address):
    """Handle incoming connection"""
    log_msg(f"=" * 60)
    log_msg(f"NEW CONNECTION from {client_address[0]}:{client_address[1]}")
    log_msg(f"=" * 60)
    
    try:
        # Set timeout for receiving
        client_socket.settimeout(30)
        
        all_data = b''
        
        while True:
            try:
                data = client_socket.recv(4096)
                if not data:
                    log_msg("Connection closed by client")
                    break
                
                all_data += data
                
                log_msg(f"Received {len(data)} bytes:")
                hex_dump(data)
                
                # Try to decode as text
                try:
                    text = data.decode('utf-8', errors='replace')
                    log_msg(f"As text: {repr(text)}")
                except:
                    pass
                
                # Send a simple acknowledgment (try different responses)
                # Some devices expect specific responses
                
                # Check if it looks like HTTP
                if data.startswith(b'GET ') or data.startswith(b'POST '):
                    log_msg(">>> Looks like HTTP request! <<<")
                    response = b"HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\n\r\nOK"
                    client_socket.send(response)
                    log_msg(f"Sent HTTP OK response")
                else:
                    # Try sending OK
                    client_socket.send(b"OK\n")
                    log_msg("Sent 'OK' response")
                
            except socket.timeout:
                log_msg("No more data (timeout)")
                break
            except Exception as e:
                log_msg(f"Receive error: {e}")
                break
        
        if all_data:
            # Save to file for analysis
            filename = f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bin"
            with open(filename, 'wb') as f:
                f.write(all_data)
            log_msg(f"Saved capture to: {filename}")
        
    except Exception as e:
        log_msg(f"Handler error: {e}")
    finally:
        client_socket.close()
        log_msg(f"Connection closed")
        log_msg("")

def start_server(port):
    """Start the raw TCP server"""
    log_msg("=" * 60)
    log_msg("HIP Device Raw TCP Listener")
    log_msg("=" * 60)
    log_msg(f"Listening on port {port}")
    log_msg("This will capture ANY data the device sends")
    log_msg("Press Ctrl+C to stop")
    log_msg("")
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind(('0.0.0.0', port))
        server.listen(5)
        log_msg(f"Server listening on 0.0.0.0:{port}")
        log_msg("Waiting for device to connect...")
        log_msg("")
        
        while True:
            client_socket, client_address = server.accept()
            # Handle each connection in a new thread
            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address)
            )
            client_thread.daemon = True
            client_thread.start()
            
    except KeyboardInterrupt:
        log_msg("Server stopped by user")
    except Exception as e:
        log_msg(f"Server error: {e}")
    finally:
        server.close()

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9090
    start_server(port)

if __name__ == "__main__":
    main()
