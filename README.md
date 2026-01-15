# HIP Upload System

A hybrid cloud attendance system that bridges legacy biometric hardware (HIP/ZKTeco devices) with a modern cloud database. The system captures attendance data from biometric devices and uploads it to a remote MySQL database, supporting both scheduled batch processing and real-time data transfer.

## Features

- **Real-time Data Transfer**: Direct HTTP communication with biometric devices
- **Scheduled Sync**: Batch processing of local log files at configurable intervals
- **Cloud Database Integration**: Direct insertion into MySQL databases
- **Device Communication**: Handles device handshake and data formatting
- **Flexible Deployment**: Can run as standalone scripts or Windows services

## Architecture Components

### `device_server.py`
A Python HTTP server that acts as a micro-service bridge, listening on port 9090 for data from HIP devices and directly inserting data into the cloud MySQL database.

### `device_snipper.py`
A debugging tool that captures and displays raw data from devices for troubleshooting and understanding data format.

### `sync_to_cloud.py`
A scheduled sync service that processes local log files from HIP Premium Time software and uploads to cloud database.

### `test_cloud_db.py`
A simple connectivity test script to verify connection to the cloud MySQL database.

## Prerequisites

- Python 3.x
- MySQL Connector for Python: `pip install mysql-connector-python`

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure database credentials and paths in the respective scripts
4. Run the desired component:
   - For real-time bridging: `python device_server.py`
   - For scheduled sync: `python sync_to_cloud.py`
   - For debugging: `python device_snipper.py`

## Deployment

The system can be deployed as Windows services using NSSM (Non-Sucking Service Manager) for automatic startup and crash recovery.

## Contributing

Feel free to submit issues and enhancement requests.

## License

[Specify your license here]