"""
Simple port scanner to check which ports are open on the HIP device
"""
import socket
import sys

def check_port(ip, port, timeout=3):
    """Check if a port is open"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except:
        return False

def main():
    # Default IP or use command line argument
    ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.100.166"
    
    print(f"Scanning ports on {ip}...")
    print("-" * 40)
    
    # Common ports for ZKTeco/HIP devices
    ports_to_check = [
        (80, "HTTP Web"),
        (443, "HTTPS"),
        (4370, "ZKTeco SDK Default"),
        (4371, "ZKTeco SDK Alt"),
        (4307, "Your Configured Port"),
        (5005, "HIP Device Default"),
        (8080, "HTTP Alt"),
        (8000, "HTTP Alt 2"),
    ]
    
    open_ports = []
    
    for port, desc in ports_to_check:
        status = check_port(ip, port)
        status_text = "OPEN" if status else "closed"
        marker = " <-- !!!" if status else ""
        print(f"  Port {port:5d} ({desc:20s}): {status_text}{marker}")
        if status:
            open_ports.append((port, desc))
    
    print("-" * 40)
    
    if open_ports:
        print(f"\nFound {len(open_ports)} open port(s):")
        for port, desc in open_ports:
            print(f"  - Port {port}: {desc}")
        
        # Suggest next step
        print("\nSuggested next step:")
        if any(p[0] in [80, 8080, 8000] for p in open_ports):
            print("  The device has HTTP port open - it may use HTTP API instead of TCP SDK.")
            print("  Try accessing http://" + ip + " in a browser.")
        if any(p[0] in [4370, 4371, 5005, 4307] for p in open_ports):
            first_sdk_port = next(p[0] for p in open_ports if p[0] in [4370, 4371, 5005, 4307])
            print(f"  Try: python hip_device_puller.py test {ip} {first_sdk_port}")
    else:
        print("\nNo ports are open! Possible issues:")
        print("  1. Device firewall is blocking connections")
        print("  2. Device is not configured for external connections")
        print("  3. Network/VLAN issue between your notebook and device")
        print("  4. Device TCP service is disabled")
        print("\nTry:")
        print("  - Check device network settings")
        print("  - Ensure 'TCP Enable' or similar option is ON in device settings")

if __name__ == "__main__":
    main()
