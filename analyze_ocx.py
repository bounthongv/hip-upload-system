"""
Deep OCX Analyzer
Extracts ASCII and Unicode strings from binary files to find protocol commands.
"""
import sys
import re
import os

def analyze_file(filename):
    print(f"Analyzing {filename}...")
    print("=" * 60)
    
    if not os.path.exists(filename):
        print("File not found!")
        return

    with open(filename, 'rb') as f:
        data = f.read()

    # 1. Search for ASCII strings (4+ chars)
    # Good for protocol commands like "CONNECT", "POST", "GET"
    ascii_strings = re.findall(b'[ -~]{4,}', data)
    
    # 2. Search for Unicode (UTF-16LE) strings
    # Windows apps use this internally. Looks like "C\x00O\x00N\x00N\x00"
    unicode_strings = re.findall(b'(?:[\x20-\x7E]\x00){4,}', data)

    print(f"Found {len(ascii_strings)} ASCII strings")
    print(f"Found {len(unicode_strings)} Unicode strings")
    print("-" * 60)

    # Keywords to look for
    keywords = [
        'connect', 'server', 'push', 'realtime', 'ack', 'nack', 
        'cmd', 'hello', 'welcome', 'version', 'get', 'post', 
        'http', 'tcp', 'udp', 'socket', 'handshake', 'error',
        'machine', 'device', 'sn', 'pass', 'user', 'att', 'log'
    ]

    print("POTENTIAL PROTOCOL COMMANDS FOUND:")
    
    # Filter and print interesting ASCII
    for s in ascii_strings:
        try:
            text = s.decode('ascii')
            # Check if it looks like a command (uppercase, no spaces, or specific format)
            if (text.isupper() and len(text) < 20) or any(k in text.lower() for k in keywords):
                print(f"  ASCII:   {text}")
        except:
            pass

    # Filter and print interesting Unicode
    for s in unicode_strings:
        try:
            text = s.decode('utf-16le')
            if any(k in text.lower() for k in keywords) or (text.isupper() and len(text) < 20):
                print(f"  UNICODE: {text}")
        except:
            pass

    print("=" * 60)

if __name__ == "__main__":
    # Target specific files
    base_dir = r"D:\hipupload\HIPPremiumTime-2.0.4\dll"
    files = [
        os.path.join(base_dir, "RealSvrOcxTcp.ocx"),
        os.path.join(base_dir, "ETC", "tcpcomm.dll"),
        os.path.join(base_dir, "ETC", "commpro.dll")
    ]
    
    for f in files:
        if os.path.exists(f):
            analyze_file(f)
            print("\n")
