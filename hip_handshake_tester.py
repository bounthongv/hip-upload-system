"""
HIP Device Protocol Handshake Tester

The device connects but sends nothing. This means WE need to initiate
the conversation. Let's try different handshake protocols.
"""
import socket
import threading
import time
import sys
from datetime import datetime

def log_msg(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    sys.stdout.flush()

def hex_dump(data, label=""):
    """Pretty print hex dump"""
    if not data:
        return
    
    hex_str = ' '.join(f'{b:02x}' for b in data)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
    
    if label:
        print(f"{label}:")
    print(f"  HEX: {hex_str}")
    print(f"  ASCII: {ascii_str}")
    print(f"  Length: {len(data)} bytes")

def try_handshakes(sock):
    """Try various handshake protocols"""
    
    handshakes = [
        ("Simple query", b"?\n"),
        ("Device info request", b"INFO\n"),
        ("Status request", b"STATUS\n"),
        ("ZK get request", b"GET\n"),
        ("Empty line", b"\n"),
        ("HIP query", b"HIP?\n"),
        ("Version query", b"VERSION\n"),
        ("Data request", b"DATA\n"),
        ("Attendance request", b"ATT\n"),
        ("Hello", b"HELLO\n"),
        # Binary handshakes
        ("NULL byte", b"\x00"),
        ("ACK", b"\x06"),
        ("ENQ", b"\x05"),
        # ZKTeco style
        ("ZK connect", bytes.fromhex('5050827d08000000e803000000000000')),
    ]
    
    for name, handshake in handshakes:
        log_msg(f"Trying: {name}")
        hex_dump(handshake, "  Sending")
        
        try:
            sock.send(handshake)
            sock.settimeout(3)
            
            try:
                response = sock.recv(4096)
                if response:
                    log_msg(f"  >>> GOT RESPONSE! <<<")
                    hex_dump(response, "  Received")
                    
                    # Try to decode
                    try:
                        text = response.decode('utf-8', errors='replace')
                        log_msg(f"  Text: {repr(text)}")
                    except:
                        pass
                    
                    # Save this successful handshake
                    filename = f"success_{name.replace(' ', '_')}_{datetime.now().strftime('%H%M%S')}.txt"
                    with open(filename, 'w') as f:
                        f.write(f"Handshake: {name}\n")
                        f.write(f"Sent: {handshake.hex()}\n")
                        f.write(f"Received: {response.hex()}\n")
                        f.write(f"Text: {repr(text if 'text' in locals() else 'N/A')}\n")
                    
                    log_msg(f"  Saved to: {filename}")
                    return True, name, handshake, response
                    
            except socket.timeout:
                log_msg(f"  No response")
                
        except Exception as e:
            log_msg(f"  Error: {e}")
        
        time.sleep(0.5)
    
    return False, None, None, None

def handle_client(client_socket, client_address):
    """Handle incoming connection"""
    log_msg("=" * 60)
    log_msg(f"DEVICE CONNECTED: {client_address[0]}:{client_address[1]}")
    log_msg("=" * 60)
    log_msg("Device opened connection but sent nothing.")
    log_msg("Trying various handshakes to initiate communication...")
    log_msg("")
    
    try:
        # Wait a moment to see if device sends first
        client_socket.settimeout(2)
        try:
            initial_data = client_socket.recv(1024)
            if initial_data:
                log_msg("Device sent data first:")
                hex_dump(initial_data)
            else:
                log_msg("Device waiting for server to send first")
        except socket.timeout:
            log_msg("Device waiting for server to send first")
        
        log_msg("")
        log_msg("Starting handshake attempts...")
        log_msg("-" * 60)
        
        success, name, sent, received = try_handshakes(client_socket)
        
        log_msg("-" * 60)
        
        if success:
            log_msg(f"SUCCESS! Device responds to: {name}")
            log_msg("Now continuing communication...")
            
            # Continue the conversation
            client_socket.settimeout(30)
            while True:
                try:
                    data = client_socket.recv(4096)
                    if not data:
                        break
                    log_msg("Received more data:")
                    hex_dump(data)
                except socket.timeout:
                    log_msg("No more data")
                    break
        else:
            log_msg("FAILED: Device didn't respond to any handshake")
            log_msg("")
            log_msg("Possible issues:")
            log_msg("  1. Device expects a specific proprietary handshake")
            log_msg("  2. Device is in wrong mode (needs ADMS/Push enabled)")
            log_msg("  3. Port 9090 is not the data push port")
            log_msg("  4. Device uses HTTP but expects specific headers")
        
    except Exception as e:
        log_msg(f"Handler error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client_socket.close()
        log_msg("Connection closed")
        log_msg("")

def start_server(port):
    """Start the server"""
    log_msg("=" * 60)
    log_msg("HIP Device Handshake Tester")
    log_msg("=" * 60)
    log_msg(f"Port: {port}")
    log_msg("Strategy: Device connects but waits - we initiate handshake")
    log_msg("Press Ctrl+C to stop")
    log_msg("")
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind(('0.0.0.0', port))
        server.listen(5)
        log_msg(f"Listening on 0.0.0.0:{port}")
        log_msg("Waiting for device...")
        log_msg("")
        
        while True:
            client_socket, client_address = server.accept()
            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address)
            )
            client_thread.daemon = True
            client_thread.start()
            
    except KeyboardInterrupt:
        log_msg("Stopped by user")
    except Exception as e:
        log_msg(f"Server error: {e}")
    finally:
        server.close()

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9090
    start_server(port)

if __name__ == "__main__":
    main()
