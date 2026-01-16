### Part 2: Implementation Documentation

# Hybrid Cloud Attendance System: Implementation Guide

## 1. Architecture Overview
This system integrates legacy biometric hardware with a modern cloud database. It utilizes the vendor's software to handle hardware communication and a background service to handle cloud data injection.

*   **Hardware Layer:** HIP/ZKTeco Devices (LAN Mode).
*   **Collection Layer:** HIP Premium Time (Windows).
*   **Transport Layer:** Custom Bridge Service (Python).
*   **Storage Layer:** Cloud MySQL Database.

## 2. Cloud Database Preparation
The local bridge service requires direct access to the cloud database port.

1.  **Identify Database Host:**
    *   Ensure you use the direct Database IP/Host (e.g., `mysql.us.cloudlogin.co`), not the website domain.
2.  **Whitelist IP Address:**
    *   Navigate to your Cloud Control Panel -> **Remote MySQL**.
    *   Add Access Host: `0.0.0.0` (Recommended for dynamic office IPs) or your specific static IP.
3.  **Verify User Permissions:**
    *   Ensure the database user has `INSERT` and `SELECT` privileges.

## 3. Log Collection Setup (HIP Premium Time)
Configure the vendor software to output data to accessible text files.

1.  Open **HIP Premium Time**.
2.  Navigate to **Auto Download** (Toolbar Icon).
3.  **Configuration:**
    *   **Save Log:** `[Checked]` (Critical).
    *   **Save Path:** `D:\Program Files (x86)\HIPPremiumTime-2.0.4\alog\`
    *   **Schedule:** Select All Days and specific Times (e.g., 09:00, 13:00, 18:00).
4.  **Action:** Click **Save Profile** then **Start**.
5.  *Note: The HIP software must remain running on the PC (minimized).*

## 4. Bridge Service Configuration
The Bridge Service (`sync_service.py`) manages the upload process.

### Configuration Parameters (In Script)
Edit the top section of `sync_service.py` to match requirements:

*   **`UPLOAD_TIMES`**: Define specific times for cloud synchronization.
    *   *Example:* `["09:00", "12:00", "18:00"]`
    *   *Behavior:* The script stays idle in the background and only activates at these times.
*   **`IGNORE_FILES_BEFORE`**: Prevent re-uploading historical data.
    *   *Example:* `"2026-01-01"`
    *   *Behavior:* Any text log created before this date is moved to the archive folder without being uploaded to the cloud.

## 5. Service Installation (NSSM)
We use **NSSM (Non-Sucking Service Manager)** to run the Bridge script as a robust Windows Service. This ensures it starts automatically with Windows and restarts if it crashes.

### Installation Steps
1.  **Open Command Prompt as Administrator**.
2.  Navigate to the script directory:
    ```cmd
    cd /d D:\hipupload
    ```
3.  **Initialize Service Installer:**
    ```cmd
    nssm install HIPCloudSync
    ```
4.  **Configure Service Details:**
    *   **Application Path:** `D:\hipupload\venv\Scripts\python.exe`
    *   **Startup Directory:** `D:\hipupload\`
    *   **Arguments:** `sync_service.py`
    *   **Service Name:** `HIPCloudSync`
5.  **Configure Logging (Optional but Recommended):**
    *   Go to **I/O** tab.
    *   Output (stdout): `D:\hipupload\service.log`
    *   Error (stderr): `D:\hipupload\error.log`
6.  **Click:** `Install Service`.

### Starting the Service
```cmd
nssm start HIPCloudSync
```

## 6. Maintenance & Troubleshooting

*   **Check Status:** Open Windows Task Manager -> Services. Look for `HIPCloudSync`.
*   **View Logs:** Open `D:\hipupload\service.log` to see upload status and record counts.
*   **Modify Schedule:** Edit `sync_service.py`, then restart the service:
    ```cmd
    nssm restart HIPCloudSync
    ```
*   **Device Date Correction:** Ensure biometric devices are synced to the correct year (2025) via the HIP Software to prevent data filtering errors.

---

## Phase 3: Enhanced Windows Service with System Tray Controller

### 1. Overview
This enhanced approach provides a native Windows service solution without requiring external tools like NSSM. It includes both a background service and a system tray controller for easy management.

*   **Components:** Windows Service + System Tray Controller
*   **Benefits:** Native Windows integration, no external dependencies, user-friendly management
*   **Architecture:** Service runs in background, controller provides GUI management

### 2. Components

#### Service Component (`sync_to_cloud_srv.py`)
*   Runs as a native Windows service
*   Performs all the same sync operations as the original script
*   Operates independently of user login
*   Follows the same scheduling and filtering logic

#### System Tray Controller (`sync_to_cloud_controller.py`)
*   Provides system tray icon with context menu
*   Allows start/stop/restart service operations
*   Displays current service status
*   Provides user-friendly service management

### 3. Installation Process

1.  **Build Executables:**
    ```cmd
    build_executables.bat
    ```
    This creates `hip_sync_service.exe` and `hip_sync_controller.exe` in the `dist` folder.

2.  **Install Service:**
    ```cmd
    install_suite.bat
    ```
    *Must be run as Administrator* - installs and starts the Windows service.

3.  **Run Controller:**
    ```cmd
    dist\hip_sync_controller.exe
    ```
    Starts the system tray controller for service management.

### 4. Management Options

*   **Via System Tray:** Right-click the system tray icon to start/stop/restart the service
*   **Via Command Line:** Use `net start HIPSyncToCloud` or `net stop HIPSyncToCloud`
*   **Via Windows Services:** Open Services.msc and manage the "HIP Sync to Cloud Service"

### 5. Uninstallation

*   **Remove Service:** Run `uninstall_suite.bat` as Administrator
*   **Cleanup:** Manually delete the installation directory if desired

### 6. Advantages Over NSSM Approach

*   **Native Integration:** Uses Python's built-in Windows service capabilities
*   **User Interface:** Provides system tray controller for easy management
*   **No External Dependencies:** Doesn't require NSSM installation
*   **Better Control:** More granular control over service lifecycle
*   **Professional Distribution:** Can be packaged as standalone executables with PyInstaller

---

## Phase 4: Direct MS Access Database Integration

### 1. Overview
This new approach eliminates the dependency on HIP Premium Time's auto-download feature by reading directly from the MS Access database. This provides more reliable and real-time data synchronization.

*   **Source:** MS Access Database (Pm2014.mdb)
*   **Target:** Cloud MySQL Database
*   **Fields:** Preserves all original MS Access fields
*   **Schedule:** Configurable sync intervals

### 2. Database Schema

#### New Table: `access_device_logs`
This table preserves all original MS Access fields:

*   `id`: Auto-increment primary key
*   `badge_number`: Corresponds to Badgenumber from Access (employee ID)
*   `check_time`: Corresponds to checktime from Access (datetime of check-in/out)
*   `check_type`: Corresponds to checktype from Access (I=In, O=Out)
*   `verify_code`: Corresponds to verifycode from Access (verification method)
*   `sensor_id`: Corresponds to sensorid from Access (which sensor was used)
*   `work_code`: Corresponds to workcode from Access (work code assignment)
*   `device_sn`: Corresponds to sn from Access (device serial number)
*   `raw_data`: Full raw record from Access for reference
*   `server_time`: Timestamp when record was processed by server

### 3. Implementation

#### Database Connection
*   **Source:** MS Access database at `D:\Program Files (x86)\HIPPremiumTime-2.0.4\db\Pm2014.mdb`
*   **Password:** `hippmforyou`
*   **Technology:** Python with pyodbc for Access connectivity

#### Sync Process
1. Connect to MS Access database
2. Query `checkinout` table for new records since last sync
3. Transform and map fields to MySQL schema
4. Insert records into `access_device_logs` table
5. Track last sync time to avoid duplicates

### 4. Configuration

#### New Configuration Options
*   `ACCESS_DB_PATH`: Path to MS Access database
*   `ACCESS_PASSWORD`: Password for database access
*   `SYNC_INTERVAL`: How often to sync (in seconds)
*   `LAST_SYNC_FILE`: File to store last sync timestamp

### 5. Advantages Over HIP Premium Time Auto-Download

*   **Direct Access:** No dependency on HIP Premium Time software
*   **Real-time Sync:** More frequent and reliable data synchronization
*   **Complete Data:** Preserves all original Access database fields
*   **Reduced Complexity:** Eliminates intermediate file processing
*   **Better Performance:** Direct database-to-database sync
*   **Reliability:** No issues with file locks or processing delays

### 6. Setup Instructions

1.  **Create Database Table:**
    Execute the SQL from `create_access_table.sql` on your cloud MySQL database

2.  **Install Dependencies:**
    ```cmd
    pip install pyodbc
    ```

3.  **Configure Settings:**
    Update `config.json` with MS Access database settings

4.  **Run Sync Script:**
    ```cmd
    python access_to_cloud.py
    ```

### 7. Migration Strategy

*   **Phase 1:** Run both systems in parallel to validate data integrity
*   **Phase 2:** Switch to MS Access method as primary sync
*   **Phase 3:** Decommission HIP Premium Time auto-download if desired
