"""
HIP CMI F68S Protocol Analyzer

This script tries different protocols to discover how the HIP device communicates.
"""
import socket
import sys
import time

def log_msg(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def hex_dump(data, prefix=""):
    """Pretty print hex dump of data"""
    if not data:
        return
    hex_str = ' '.join(f'{b:02x}' for b in data)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
    print(f"{prefix}HEX: {hex_str}")
    print(f"{prefix}ASCII: {ascii_str}")

def test_raw_connect(ip, port, timeout=10):
    """Connect and see if device sends anything first"""
    log_msg(f"Test 1: Raw connect - checking if device sends data first...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        log_msg("Connected! Waiting for device to send data...")
        
        try:
            data = sock.recv(1024)
            if data:
                log_msg(f"Device sent {len(data)} bytes unprompted:")
                hex_dump(data, "  ")
                return data
            else:
                log_msg("Device sent empty response")
        except socket.timeout:
            log_msg("Device didn't send anything (waited 10s)")
        
        sock.close()
    except Exception as e:
        log_msg(f"Error: {e}")
    
    return None

def test_http_get(ip, port):
    """Test if device responds to HTTP GET"""
    log_msg(f"Test 2: HTTP GET request...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((ip, port))
        
        # Send HTTP GET request
        http_request = f"GET / HTTP/1.0\r\nHost: {ip}\r\n\r\n"
        log_msg(f"Sending: {repr(http_request[:50])}...")
        sock.send(http_request.encode())
        
        # Wait for response
        response = b''
        try:
            while True:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                response += chunk
        except socket.timeout:
            pass
        
        sock.close()
        
        if response:
            log_msg(f"Received {len(response)} bytes:")
            # Show first 500 bytes
            text = response[:500].decode('utf-8', errors='replace')
            print(f"  Response: {text}")
            if b'HTTP' in response or b'html' in response.lower():
                log_msg(">>> Device responds to HTTP! <<<")
                return True
        else:
            log_msg("No HTTP response")
            
    except Exception as e:
        log_msg(f"Error: {e}")
    
    return False

def test_http_iclock(ip, port):
    """Test ADMS/iclock endpoint"""
    log_msg(f"Test 3: HTTP iclock endpoint (ADMS protocol)...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((ip, port))
        
        # Send iclock request
        http_request = f"GET /iclock/cdata?SN=test HTTP/1.0\r\nHost: {ip}\r\n\r\n"
        log_msg(f"Sending iclock request...")
        sock.send(http_request.encode())
        
        response = b''
        try:
            while True:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                response += chunk
        except socket.timeout:
            pass
        
        sock.close()
        
        if response:
            log_msg(f"Received {len(response)} bytes:")
            text = response[:500].decode('utf-8', errors='replace')
            print(f"  Response: {text}")
            return True
            
    except Exception as e:
        log_msg(f"Error: {e}")
    
    return False

def test_zkteco_protocols(ip, port):
    """Test various ZKTeco protocol variants"""
    log_msg(f"Test 4: ZKTeco protocol variants...")
    
    # Different ZKTeco packet formats
    packets = [
        # Standard ZKTeco TCP with magic header
        ("ZK Magic Header", bytes.fromhex('5050827d08000000e803000000000000')),
        # Without magic (direct command)
        ("Direct Command", bytes.fromhex('e803000000000000')),
        # Old ZK protocol
        ("Old ZK", bytes.fromhex('e8030000')),
        # Connect with session 0
        ("Session 0", bytes.fromhex('5050827d10000000e80300000000000000000000')),
        # Simple ping-like
        ("Ping", b'\x00\x00\x00\x00'),
    ]
    
    for name, packet in packets:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, port))
            
            log_msg(f"  Trying: {name}")
            hex_dump(packet, "    Send: ")
            sock.send(packet)
            
            try:
                response = sock.recv(1024)
                if response:
                    log_msg(f"  Got response!")
                    hex_dump(response, "    Recv: ")
                    sock.close()
                    return name, response
            except socket.timeout:
                pass
            
            sock.close()
            
        except Exception as e:
            log_msg(f"  Error: {e}")
    
    log_msg("No ZKTeco variant worked")
    return None, None

def test_push_simulation(ip, port):
    """Simulate what happens when device connects (reverse - we act as device)"""
    log_msg(f"Test 5: Checking if port 5005 is for device PUSH (we're supposed to be server)...")
    log_msg("  This port might be for the device to RECEIVE config, not send data.")
    log_msg("  The device may expect YOU to run a server, and IT connects to you.")
    return None

def analyze_protocol(ip, port):
    """Main analysis function"""
    print("=" * 60)
    print(f"HIP CMI F68S Protocol Analyzer")
    print(f"Target: {ip}:{port}")
    print("=" * 60)
    print()
    
    # Test 1: Raw connect
    result = test_raw_connect(ip, port)
    print()
    
    # Test 2: HTTP
    is_http = test_http_get(ip, port)
    print()
    
    # Test 3: iclock
    test_http_iclock(ip, port)
    print()
    
    # Test 4: ZKTeco variants
    name, response = test_zkteco_protocols(ip, port)
    print()
    
    # Test 5: Push info
    test_push_simulation(ip, port)
    print()
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if is_http:
        print(">>> Device uses HTTP protocol on port 5005 <<<")
        print("Recommendation: Use the HTTP receiver (hip_device_receiver.py)")
        print(f"  Configure device to push to YOUR IP on port 8080")
        print(f"  Or access http://{ip}:5005 in browser to explore")
    elif name and response:
        print(f">>> Device responded to: {name} <<<")
        print("We can adapt the puller to use this protocol variant")
    else:
        print(">>> Device accepts connection but doesn't respond to known protocols <<<")
        print()
        print("Possible explanations:")
        print("  1. Port 5005 is for the device to CONNECT OUT (push mode)")
        print("     - The device connects TO a server, server doesn't connect to device")
        print("     - Solution: Run hip_device_receiver.py and configure device to push")
        print()
        print("  2. Device uses proprietary HIP protocol")
        print("     - Need HIP SDK documentation or reverse engineering")
        print()
        print("  3. Port 5005 is for HIP Premium Time software only")
        print("     - The desktop software may use a proprietary sync protocol")
        print()
        print("RECOMMENDED NEXT STEP:")
        print("  1. Run: python hip_device_receiver.py")
        print("  2. Configure device network settings:")
        print("     - Server IP: Your notebook's IP")
        print("     - Server Port: 8080")
        print("     - Enable Push/ADMS")
        print("  3. The DEVICE will push data TO your server")

def main():
    ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.100.166"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5005
    
    analyze_protocol(ip, port)

if __name__ == "__main__":
    main()
