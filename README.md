# HIP Upload System

A hybrid cloud attendance system that bridges legacy biometric hardware (HIP/ZKTeco devices) with a modern cloud database. The system captures attendance data from biometric devices and uploads it to a remote MySQL database, supporting both scheduled batch processing and real-time data transfer.

## Features

- **Real-time Data Transfer**: Direct HTTP communication with biometric devices
- **Scheduled Sync**: Batch processing of local log files at configurable intervals
- **Cloud Database Integration**: Direct insertion into MySQL databases
- **Device Communication**: Handles device handshake and data formatting
- **Flexible Deployment**: Can run as standalone scripts, Windows services, or packaged executables

## Architecture Components

### `device_server.py`
A Python HTTP server that acts as a micro-service bridge, listening on port 9090 for data from HIP devices and directly inserting data into the cloud MySQL database.

### `device_server_srv.py`
A Windows service version of the device server functionality that can run in the background without a GUI.

### `device_server_controller.py`
A system tray application that provides a user-friendly interface to manage the device server Windows service.

### `device_sniffer.py`
A debugging tool that captures and displays raw data from devices for troubleshooting and understanding data format.

### `sync_to_cloud.py`
A scheduled sync service that processes local log files from HIP Premium Time software and uploads to cloud database.

### `sync_to_cloud_srv.py`
A Windows service version of the sync functionality that can run in the background without a GUI.

### `sync_to_cloud_controller.py`
A system tray application that provides a user-friendly interface to manage the Windows service.

### `test_cloud_db.py`
A simple connectivity test script to verify connection to the cloud MySQL database.

## Prerequisites

- Python 3.x
- Required packages: `pip install -r requirements.txt`

## Security Implementation

### Credential Protection
This application implements credential encryption to protect sensitive database information:

- **Public Configuration** (`config.json`): Contains user-modifiable settings like sync times and file paths
- **Encrypted Credentials** (`encrypted_credentials.bin`): Contains sensitive database credentials in encrypted format
- **Encryption Method**: Uses Fernet symmetric encryption from the cryptography library

### Updating Credentials
To update credentials:
1. Modify your local `credentials.json` file with new database information
2. Run the encryption script: `python encrypt_credentials.py`
3. This generates `encrypted_credentials.bin` for distribution
4. Replace the existing `encrypted_credentials.bin` in the application directory

### Security Notes
- The encryption key is embedded in the application binary during compilation
- Only authorized personnel should have access to the encryption script
- Regular users cannot access or modify the encrypted credentials

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure database credentials and paths in the respective scripts
4. Run the desired component:
   - For real-time bridging: `python device_server.py`
   - For scheduled sync: `python sync_to_cloud.py`
   - For debugging: `python device_sniffer.py`

## Deployment Options

### Option 1: Standalone Scripts
Run directly as Python scripts for testing and development.

### Option 2: Windows Service with System Tray Controller (Recommended)
For production use with user-friendly management:

1. Build executables: `build_executables.bat`
2. Install sync service: `install_suite.bat` (run as Administrator)
3. Install device service: `install_device_service.bat` (run as Administrator)
4. Run controllers: `dist\hip_sync_controller.exe` or `dist\hip_device_controller.exe`

This approach provides:
- Native Windows service integration
- System tray controller for easy management
- No external dependencies like NSSM
- Professional distribution as standalone executables

### Option 3: Traditional Windows Service
Using NSSM (Non-Sucking Service Manager) as described in the documentation.

## Building Executables

To create standalone executables using PyInstaller:
1. Run `build_executables.bat`
2. Find executables in the `dist` folder
3. Distribute the executables without requiring Python installation

## Documentation

Detailed implementation guides are available in the `docs/` directory:
- Phase 1: Batch processing implementation (sync_to_cloud)
- Phase 2: Real-time bridge implementation (device_server)
- Phase 3: Enhanced Windows service with system tray controller (sync_to_cloud)
- Phase 3: Enhanced Windows service with system tray controller (device_server)

## Contributing

Feel free to submit issues and enhancement requests.

## License

[Specify your license here]