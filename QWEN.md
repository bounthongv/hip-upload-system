# HIP Upload System - Project Overview

## Project Purpose
This is a hybrid cloud attendance system that bridges legacy biometric hardware (HIP/ZKTeco devices) with a modern cloud database. The system captures attendance data from biometric devices and uploads it to a remote MySQL database, supporting both scheduled batch processing and real-time data transfer.

## Architecture Components

### 1. `device_server.py`
- A Python HTTP server that acts as a micro-service bridge
- Listens on port 9090 for data from HIP devices
- Receives attendance logs via HTTP POST requests
- Directly inserts data into the cloud MySQL database
- Handles device handshake/config requests via HTTP GET
- Includes error handling and connection management

### 2. `device_snipper.py` (likely typo for "sniffer")
- A debugging/sniffing tool that captures and displays raw data from devices
- Used to verify device connectivity and understand data format
- Does not upload data to cloud, just logs for inspection
- Essential for troubleshooting device communication

### 3. `sync_to_cloud.py`
- A scheduled sync service that processes local log files
- Monitors the HIP Premium Time software's log directory
- Reads attendance data from text files and uploads to cloud database
- Runs continuously with scheduled upload times (09:00, 12:00, 17:00, 22:00)
- Includes file filtering to avoid re-uploading old data

### 4. `test_cloud_db.py`
- A simple connectivity test script
- Verifies connection to the cloud MySQL database
- Used for troubleshooting database access issues

## Dependencies
- `mysql-connector-python` - for database connections
- Standard Python libraries: `http.server`, `mysql.connector`, `os`, `glob`, `shutil`, `datetime`, etc.

## Configuration
The system requires configuration of:
- Cloud database credentials and host
- Local log directory paths
- Scheduled upload times
- Device IP addresses and ports

## Deployment Options
1. **Service Mode**: Deployed as Windows services using NSSM (Non-Sucking Service Manager)
2. **Direct Execution**: Scripts can be run directly for testing/debugging

## Key Features
- Real-time data transfer from biometric devices
- Scheduled batch processing of historical logs
- Automatic file archiving after successful upload
- Device handshake/handshake response handling
- Error logging and connection resilience
- Filtering of old data to prevent duplicate uploads

## Usage Scenarios
1. **Real-time Bridge**: Use `device_server.py` for immediate data transfer from devices
2. **Batch Processing**: Use `sync_to_cloud.py` for scheduled uploads of existing logs
3. **Debugging**: Use `device_snipper.py` to inspect raw device communications
4. **Testing**: Use `test_cloud_db.py` to verify database connectivity

## Documentation
Additional implementation details and setup instructions are available in the `/docs` directory:
- `1-phase1-upload-log.md` - Batch processing implementation guide
- `2-micro-server.md` - Real-time bridge implementation guide