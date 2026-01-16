# HIP Upload System

## Project Overview
The HIP Upload System is a hybrid cloud attendance solution designed to bridge legacy biometric hardware (HIP/ZKTeco devices) with a modern cloud MySQL database. It supports both real-time data capture via a custom HTTP micro-service and scheduled batch processing of local log files. The system is designed to run on Windows, offering deployment options as standalone Python scripts or as fully integrated Windows Services with system tray controllers.

## Architecture & Components

The system is composed of two main subsystems:

### 1. Real-time Device Bridge
*   **`device_server.py`**: A Python HTTP server listening on port 9090. It receives data directly from HIP devices and inserts it into the cloud database.
*   **`device_server_srv.py`**: The Windows Service wrapper for the device server.
*   **`device_server_controller.py`**: System tray application for managing the device server service.

### 2. Scheduled Batch Sync
*   **`sync_to_cloud.py`**: A script that processes local log files from HIP Premium Time software and uploads them to the cloud database at configured intervals.
*   **`sync_to_cloud_srv.py`**: The Windows Service wrapper for the sync process.
*   **`sync_to_cloud_controller.py`**: System tray application for managing the sync service.

### Utilities
*   **`device_sniffer.py`**: Debugging tool to capture and view raw device traffic.
*   **`test_cloud_db.py`**: Connectivity test for the cloud database.
*   **`build_executables.bat`**: Script to build standalone executables using PyInstaller.

## Development & Setup

### Prerequisites
*   Python 3.x
*   Windows OS (required for Service and Tray functionality)

### Installation
1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    Key dependencies: `mysql-connector-python`, `pywin32`, `pyodbc`.

2.  **Configuration:**
    *   **`config.json`**: Configure local log directories and upload schedules.
        ```json
        {
            "LOG_DIR": "D:\\path\\to\\logs",
            "UPLOAD_TIMES": ["09:00", "13:30", "17:00", "22:00"]
        }
        ```
    *   **`credentials.json`**: (Ensure this exists and is configured with database credentials)

### Running the Application

#### Option 1: Development (Standalone Scripts)
Run components directly for testing:
*   **Device Server:** `python device_server.py`
*   **Sync Process:** `python sync_to_cloud.py`
*   **Sniffer (Debug):** `python device_sniffer.py`

#### Option 2: Production (Windows Services)
1.  **Build Executables:**
    Run `build_executables.bat` to generate `.exe` files in the `dist/` directory.

2.  **Install/Manage Services:**
    *   **Install Sync Service:** Run `install_suite.bat` (as Administrator).
    *   **Install Device Service:** Run `install_device_service.bat` (as Administrator).
    *   **Run Controllers:** Launch `dist\hip_sync_controller.exe` or `dist\hip_device_controller.exe`.

## Key Files
*   `README.md`: Main project documentation.
*   `requirements.txt`: Python package dependencies.
*   `config.json`: Application configuration.
*   `build_executables.bat`: Build script for PyInstaller.
*   `docs/`: Detailed documentation for specific implementation phases.
