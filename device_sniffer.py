from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
import sys

# --- CONFIGURATION ---
LOCAL_IP = '0.0.0.0'
LOCAL_PORT = 9090  # You chose 9090

class DeviceHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Clean console output
        return

    def do_POST(self):
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔥 POST REQUEST RECEIVED!")

        # 1. Read Headers
        length = int(self.headers.get('Content-Length', 0))
        print(f"   path: {self.path}")
        print(f"   content-type: {self.headers.get('Content-Type')}")

        # 2. Read Body
        if length > 0:
            body = self.rfile.read(length).decode('utf-8', errors='ignore')
            print(f"   👇 RAW DATA FROM DEVICE 👇")
            print("   -------------------------------------------------")
            print(f"{body}")
            print("   -------------------------------------------------")
        else:
            print("   (Empty Body)")

        # 3. Reply OK
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")

    def do_GET(self):
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ⚡ GET REQUEST (Handshake)")
        print(f"   path: {self.path}")

        # Send Config to wake up the device
        # Note: 'ATTLOGStamp=0' forces it to upload ALL history
        response = (
            "GET OPTION FROM: SN\n"
            "ATTLOGStamp=0\n"
            "OPERLOGStamp=0\n"
            "ATTPHOTOStamp=0\n"
            "ErrorDelay=30\n"
            "Delay=10\n"
            "TransTimes=00:00;14:05\n"
            "TransInterval=1\n"
            "TransFlag=1111000000\n"
            "Realtime=1\n"
            "Encrypt=0\n"
        )
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(response.encode())
        print("   -> Sent Configuration Commands")

    def do_HEAD(self):
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🟡 HEAD REQUEST (Ping)")
        # Return 405 Method Not Allowed to force device to use GET/POST
        self.send_response(405)
        self.end_headers()
        print("   -> Sent 405 to force GET")

if __name__ == "__main__":
    print(f"👀 SNIFFER running on Port {LOCAL_PORT}...")
    print("   Waiting for device...")
    server = HTTPServer((LOCAL_IP, LOCAL_PORT), DeviceHandler)
    server.serve_forever()
