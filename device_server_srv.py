from http.server import BaseHTTPRequestHandler, HTTPServer
import mysql.connector
from datetime import datetime
import sys
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket

# --- CONFIGURATION ---

# 1. LOCAL SERVER SETTINGS
LOCAL_IP = '0.0.0.0' # Listen on all network interfaces
LOCAL_PORT = 9090    # Device must send to this port

# 2. CLOUD DATABASE (Destination)
DB_CONFIG = {
    'user': 'apis_misuzu2',
    'password': 'Tw0NC35pu*',
    'host': 'mysql.us.cloudlogin.co',
    'database': 'apis_misuzu2',
    'port': 3306,
    'raise_on_warnings': True,
    'connection_timeout': 30
}

# --- DATABASE LOGIC ---
def insert_to_cloud(user_id, check_time, status=0, verify=1, raw_data=""):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        sql = ("INSERT IGNORE INTO device_logs "
               "(device_sn, user_id, check_time, status, verify_type, raw_data) "
               "VALUES (%s, %s, %s, %s, %s, %s)")

        # We hardcode the SN since we know which site this is running at
        val = ('HIP_DEVICE_1', user_id, check_time, status, verify, raw_data)

        cursor.execute(sql, val)
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ DB Error: {e}")
        return False

# --- HTTP HANDLER (The "Listener") ---
class DeviceHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Override to print to console with timestamp
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {format % args}")

    def do_POST(self):
        """Handle Data Upload (ATTLOG)"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')

        # print(f"Received Data: {post_data}") # Debugging

        lines = post_data.split('\n')
        count = 0

        for line in lines:
            line = line.strip()
            if not line: continue

            # Format: ID <tab> Time <tab> Status <tab> Verify
            parts = line.split('\t')
            if len(parts) >= 2:
                u_id = parts[0]
                c_time = parts[1]
                stat = parts[2] if len(parts) > 2 else 0
                veri = parts[3] if len(parts) > 3 else 1

                if insert_to_cloud(u_id, c_time, stat, veri, line):
                    count += 1

        print(f"✅ Saved {count} records to Cloud.")

        # Reply "OK" to device so it clears the log
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")

    def do_GET(self):
        """Handle Handshake/Config"""
        # The device asks: "Do you have any commands for me?"
        # We assume the SN is passed in URL, but we reply generically

        print("⚡ Device Handshake received.")

        response_text = (
            "GET OPTION FROM: SN\n"
            "ATTLOGStamp=0\n"
            "OPERLOGStamp=0\n"
            "ATTPHOTOStamp=0\n"
            "ErrorDelay=30\n"
            "Delay=10\n"
            "TransTimes=00:00;14:05\n"
            "TransInterval=1\n"
            "TransFlag=1111000000\n"
            "TimeZone=7\n"
            "Realtime=1\n"
            "Encrypt=0\n"
        )

        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(response_text.encode())

    def do_HEAD(self):
        """Handle Connectivity Check"""
        # Force device to use GET/POST
        self.send_response(405)
        self.end_headers()

class DeviceServerService(win32serviceutil.ServiceFramework):
    _svc_name_ = "HIPDeviceServer"
    _svc_display_name_ = "HIP Device Server Service"
    _svc_description_ = "Handles HIP device communications and syncs to cloud database"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.is_alive = True
        self.httpd = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_alive = False
        if self.httpd:
            self.httpd.shutdown()

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.main()

    def main(self):
        print(f"🚀 Device Listener running on Port {LOCAL_PORT}...")
        print(f"👉 Point your Device Server IP to this computer's IP.")
        print("-------------------------------------------------------")
        
        server_address = (LOCAL_IP, LOCAL_PORT)
        self.httpd = HTTPServer(server_address, DeviceHandler)
        
        try:
            while self.is_alive:
                # Handle one request at a time to allow checking for stop signal
                self.httpd.handle_request()
                
                # Check if stop signal was received
                if win32event.WaitForSingleObject(self.hWaitStop, 100) == win32event.WAIT_OBJECT_0:
                    break
        except KeyboardInterrupt:
            pass
        finally:
            if self.httpd:
                self.httpd.server_close()
        
        print("Device server stopped.")

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(DeviceServerService)