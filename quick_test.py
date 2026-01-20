"""
Quick test of most promising Packet 12 values
"""
import socket
import time

def test_value(ip, var_bytes_hex):
    """Test one specific Packet 12 value"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)

    try:
        sock.connect((ip, 5005))

        # 1. Handshake
        pkt8 = bytes.fromhex("55 aa 01 b0 00 00 00 00 00 00 ff ff 00 00 17 00")
        sock.send(pkt8)
        sock.recv(1024)
        time.sleep(0.1)

        # 2. Setup
        pkt10 = bytes.fromhex("55 aa 01 b4 00 00 00 00 00 00 ff ff 00 00 18 00")
        sock.send(pkt10)
        sock.recv(1024)
        time.sleep(0.2)

        # 3. Build and send Packet 12
        var_bytes = bytes.fromhex(var_bytes_hex)
        pkt12 = bytes.fromhex("55 aa 01 a4") + var_bytes + bytes.fromhex("19 00")

        print(f"\nTesting: {var_bytes_hex}")
        print(f"Sending: {pkt12.hex()}")

        sock.send(pkt12)

        # 4. Try to receive
        sock.settimeout(15)
        data = sock.recv(65535)

        if data:
            print(f"Response: {len(data)} bytes")
            if len(data) > 20:
                print(f"SUCCESS! First 32 bytes: {data[:32].hex()}")
                return data
            else:
                print(f"Small response: {data.hex()}")
        else:
            print("No response (timeout)")

        return None

    except socket.timeout:
        print("Timeout waiting for response")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None
    finally:
        sock.close()

def main():
    ip = "192.168.100.166"

    # Most promising values to test
    test_values = [
        # Original from Wireshark
        "00000005200000000041",
        # Variations with token 03 from Packet 11
        "00000003200000000041",
        "00000003200000000003",
        "03000000200000000041",
        # Try without 0x20
        "00000005000000000041",
        "00000003000000000003",
        # Try with checksum-like endings
        "00000005200000000044",  # 0x41 + 0x03
        "00000005200000000046",  # 0x41 + 0x05
        # Try with different sequence numbers
        "00000001200000000041",
        "00000002200000000042",
        "00000003200000000043",
        "00000004200000000044",
        "00000005200000000045",
    ]

    print(f"Testing against {ip}:5005\n")

    for i, value in enumerate(test_values, 1):
        print(f"\n[{i}/{len(test_values)}] ", end="")
        result = test_value(ip, value)
        if result and len(result) > 100:
            print(f"\n🎉 SUCCESS with value: {value}")
            print(f"Got {len(result)} bytes of data!")
            break
        time.sleep(1)

if __name__ == "__main__":
    main()
