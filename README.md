# HIP Upload System

A hybrid cloud attendance system that bridges HIP biometric devices with a modern cloud database. The system reads directly from the MS Access database and uploads to a remote MySQL database, supporting scheduled data synchronization.

## Features

- **MS Access Integration**: Direct reading from HIP Premium Time MS Access database
- **Cloud Database Integration**: Direct insertion into MySQL databases
- **Scheduled Sync**: Configurable times for data synchronization
- **Secure Credentials**: Encrypted database credentials for security
- **Robust Sync**: Per-batch sync tracking to prevent data loss

## Architecture Components

### `access_to_cloud.py`
Main application that reads from MS Access database and syncs to cloud database. Runs continuously, checking for scheduled sync times.

### `encrypt_credentials.py`
Internal tool for encrypting database credentials (for authorized personnel only).

### `config.json`
Public configuration file containing user-modifiable settings (sync times, file paths, etc.)

### `encrypted_credentials.bin`
Encrypted file containing sensitive database credentials (created by encrypt_credentials.py).

### `create_access_table.sql`
SQL script to create the required table in your cloud MySQL database.

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
- The same fixed encryption key is used in both the encryption script and the application
- Only authorized personnel should have access to the encryption script
- Regular users cannot access or modify the encrypted credentials
- The encryption key is hardcoded in the application source (will be embedded when compiled)

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Create the required table in your cloud database using `create_access_table.sql`
4. Configure `config.json` with your settings
5. Generate `encrypted_credentials.bin` using the encryption script
6. Run the application: `python access_to_cloud.py`

## Distribution Guide for Team

### For Customer Deployment:
1. **Compile the application** using PyInstaller:
   ```cmd
   pyinstaller --onefile --console --name=hip_access_sync access_to_cloud.py
   ```
   This creates a single executable file that includes Python and all required libraries.
   The executable will be located in the `dist/` folder as `hip_access_sync.exe`.

2. **Prepare distribution files**:
   - `dist/hip_access_sync.exe` (compiled application - this is the only file needed)
   - `config.json` (with customer-specific settings)
   - `encrypted_credentials.bin` (with customer's encrypted database credentials)
   - `create_access_table.sql` (for database setup instructions)

3. **Provide to customer**:
   - The executable is completely self-contained - no Python installation needed
   - Install the executable as a Windows service using NSSM
   - Ensure the database table exists using the SQL script
   - Verify the config.json has correct settings for their environment

### For Internal Use (Updating Credentials):
1. Create a `credentials.json` file with the format:
   ```json
   {
     "DB_CONFIG": {
       "user": "your_username",
       "password": "your_password",
       "host": "your_host",
       "database": "your_database",
       "port": 3306,
       "raise_on_warnings": true,
       "connection_timeout": 60
     }
   }
   ```
2. Run: `python encrypt_credentials.py`
3. This creates `encrypted_credentials.bin` for distribution

## Configuration Options

### `config.json` Settings:
- `ACCESS_DB_PATH`: Path to the HIP MS Access database file
- `ACCESS_PASSWORD`: Password for the MS Access database
- `UPLOAD_TIMES`: Array of times when sync should occur (HH:MM format)
- `BATCH_SIZE`: Number of records to process in each batch
- `LAST_SYNC_FILE`: File to store last sync position

## Deployment with NSSM

To run as a Windows service:
1. Download and install NSSM
2. Run as Administrator:
   ```
   nssm install HIPAccessToCloud
   ```
3. In NSSM GUI:
   - Path: Path to your compiled executable
   - Startup directory: Directory containing config files
4. Start the service:
   ```
   nssm start HIPAccessToCloud
   ```

## Troubleshooting

- Check that the MS Access database path is correct in config.json
- Verify that the cloud database table exists using create_access_table.sql
- Ensure encrypted_credentials.bin is in the same directory as the executable
- Monitor logs for any connection or sync issues

## Contributing

Feel free to submit issues and enhancement requests.

## License

[Specify your license here]