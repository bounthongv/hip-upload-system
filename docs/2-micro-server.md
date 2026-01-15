
# Architecture: Python Micro-Server Bridge

## 1. Overview
This strategy replaces the vendor software with a custom Python listener running on a local Windows PC. It acts as a "Micro-Server" that accepts data directly from the device and pushes it to the Cloud Database.

*   **Workflow:** Device (HTTP 1.0) → Python Script (Local Port 9090) → Cloud MySQL (Port 3306).
*   **Benefit:** Real-time data, eliminates vendor software, works with complex network setups.

## 2. Requirements
*   **Windows PC:** Static Local IP (e.g., `192.168.100.55`).
*   **Cloud Database:** Remote Access enabled for IP `0.0.0.0`.
*   **Network:** Windows Firewall must allow Inbound TCP on Port **9090**.
*   **Software:** Python 3.x installed.

---

## Phase 1: The Device Sniffer (Debugging)
*Use this script first to confirm the device is connecting and to identify the exact data format.*

**File:** `D:\hipupload\device_sniffer.py`

```python
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

LOCAL_PORT = 9090

class SnifferHandler(BaseHTTPRequestHandler):
    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def do_HEAD(self):
        self.log("🟡 HEAD Request received (Ping). Sending 405 to force GET/POST.")
        self.send_response(405) # Method Not Allowed
        self.end_headers()

    def do_GET(self):
        self.log("⚡ GET Request received (Handshake). Sending Config...")
        # Force device to send all history (ATTLOGStamp=0)
        config = "GET OPTION FROM: SN\nATTLOGStamp=0\nOPERLOGStamp=0\nATTPHOTOStamp=0\nErrorDelay=30\nDelay=10\nTransTimes=00:00;14:05\nTransInterval=1\nTransFlag=1111000000\nRealtime=1\nEncrypt=0\n"
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(config.encode())

    def do_POST(self):
        self.log("🔥 POST REQUEST RECEIVED! (DATA!)")
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8', errors='ignore')
        
        print("\n--- [ RAW DATA START ] ---")
        print(body)
        print("--- [ RAW DATA END ] ---\n")

        self.send_response(200)
        self.wfile.write(b"OK")

if __name__ == "__main__":
    print(f"👀 SNIFFER listening on Port {LOCAL_PORT}...")
    server = HTTPServer(('0.0.0.0', LOCAL_PORT), SnifferHandler)
    server.serve_forever()
```

**To Run:** `py device_sniffer.py`
**Goal:** Verify you see "RAW DATA START" with attendance logs.

---

## Phase 2: The Production Bridge
*Use this script once Phase 1 confirms data flow. This connects to the Cloud Database.*

**Prerequisite:** `pip install mysql-connector-python`
**File:** `D:\hipupload\device_server.py`

```python
from http.server import BaseHTTPRequestHandler, HTTPServer
import mysql.connector
from datetime import datetime

# --- CONFIG ---
LOCAL_PORT = 9090
DB_CONFIG = {
    'user': 'apis_misuzu2',
    'password': 'Tw0NC35pu*',
    'host': 'mysql.us.cloudlogin.co',
    'database': 'apis_misuzu2',
    'port': 3306,
    'raise_on_warnings': True,
    'connection_timeout': 10
}

class ProductionHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8', errors='ignore')
        
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor()
            sql = "INSERT IGNORE INTO device_logs (device_sn, user_id, check_time, status, verify_type, raw_data) VALUES (%s, %s, %s, %s, %s, %s)"
            
            count = 0
            for line in body.split('\n'):
                line = line.strip()
                if not line: continue
                parts = line.split('\t')
                
                # Check format (ID <tab> Time <tab> Status <tab> Verify)
                if len(parts) >= 2:
                    cursor.execute(sql, ('HIP_LAN_1', parts[0], parts[1], parts[2] if len(parts)>2 else 0, parts[3] if len(parts)>3 else 1, line))
                    count += 1
            
            conn.commit()
            cursor.close()
            conn.close()
            print(f"[{datetime.now()}] Saved {count} records.")
        except Exception as e:
            print(f"[{datetime.now()}] DB Error: {e}")

        self.send_response(200)
        self.wfile.write(b"OK")

    def do_GET(self):
        # Standard Handshake
        config = "GET OPTION FROM: SN\nATTLOGStamp=0\nOPERLOGStamp=0\nATTPHOTOStamp=0\nErrorDelay=30\nDelay=10\nTransTimes=00:00;14:05\nTransInterval=1\nTransFlag=1111000000\nRealtime=1\nEncrypt=0\n"
        self.send_response(200)
        self.wfile.write(config.encode())

    def do_HEAD(self):
        self.send_response(405) # Force GET

if __name__ == "__main__":
    print(f"🚀 BRIDGE SERVICE running on Port {LOCAL_PORT}...")
    HTTPServer(('0.0.0.0', LOCAL_PORT), ProductionHandler).serve_forever()
```

---

## 3. Device Configuration
Configure the physical HIP Device to point to the Windows PC.

1.  **Menu** → **Network**.
2.  **Server IP:** Enter the Local IP of the Windows PC (e.g., `192.168.100.55`).
3.  **Server Port:** `9090`.
4.  **Mode:** LAN.

---

## Phase 3: Enhanced Windows Service with System Tray Controller

### 1. Overview
This enhanced approach provides a native Windows service solution for the device server without requiring external tools. It includes both a background service and a system tray controller for easy management.

*   **Components:** Windows Service + System Tray Controller
*   **Benefits:** Native Windows integration, no external dependencies, user-friendly management
*   **Architecture:** Service runs in background, controller provides GUI management

### 2. Components

#### Service Component (`device_server_srv.py`)
*   Runs as a native Windows service
*   Performs all the same device communication as the original script
*   Operates independently of user login
*   Listens on port 9090 for device connections
*   Handles device handshake and data uploads to cloud database

#### System Tray Controller (`device_server_controller.py`)
*   Provides system tray icon with context menu
*   Allows start/stop/restart service operations
*   Displays current service status
*   Provides user-friendly service management

### 3. Installation Process

1.  **Build Executables:**
    ```cmd
    build_executables.bat
    ```
    This creates `hip_device_service.exe` and `hip_device_controller.exe` in the `dist` folder.

2.  **Install Service:**
    ```cmd
    install_device_service.bat
    ```
    *Must be run as Administrator* - installs and starts the Windows service.

3.  **Run Controller:**
    ```cmd
    dist\hip_device_controller.exe
    ```
    Starts the system tray controller for service management.

### 4. Management Options

*   **Via System Tray:** Right-click the system tray icon to start/stop/restart the service
*   **Via Command Line:** Use `net start HIPDeviceServer` or `net stop HIPDeviceServer`
*   **Via Windows Services:** Open Services.msc and manage the "HIP Device Server Service"

### 5. Uninstallation

*   **Remove Service:** Run `uninstall_device_service.bat` as Administrator
*   **Cleanup:** Manually delete the installation directory if desired

### 6. Advantages Over Standalone Script Approach

*   **Native Integration:** Uses Python's built-in Windows service capabilities
*   **User Interface:** Provides system tray controller for easy management
*   **No External Dependencies:** Doesn't require additional tools
*   **Better Control:** More granular control over service lifecycle
*   **Professional Distribution:** Can be packaged as standalone executables with PyInstaller

## 4. Legacy Deployment (NSSM)
Use **NSSM** to ensure the Python script runs automatically on boot. This is the older approach that requires external tools.

1.  Open CMD as Administrator.
2.  `nssm install HIPListener`
3.  **Application Path:** `D:\hipupload\venv\Scripts\python.exe`
4.  **Arguments:** `D:\hipupload\device_server.py`
5.  **Start:** `nssm start HIPListener`

---

## 5. Modern Deployment (Enhanced Service)
For the new enhanced approach without external dependencies, see Phase 3 above.
