# AGENTS.md - Development Guidelines for HIP Upload System

This file contains build commands, code style guidelines, and development conventions for agentic coding agents working on this repository.

## Build & Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt
```

### Running Applications
```bash
# Main access-to-cloud sync service
python access_to_cloud.py

# Legacy log file sync service  
python sync_to_cloud.py

# Test database connection
python test_cloud_db.py

# Run with batch scripts (recommended)
run_access_sync.bat
```

### Building Executables
```bash
# Compile to standalone executable
pyinstaller --onefile --console --name=access_to_cloud_service access_to_cloud.py

# Or use the provided batch script
compile_for_nssm.bat
```

### Testing
```bash
# Test database connectivity
python test_cloud_db.py

# No formal test framework - use manual testing and log verification
```

## Code Style Guidelines

### Import Organization
- Standard library imports first (os, sys, time, datetime, json)
- Third-party imports second (pyodbc, pymysql, cryptography)
- Group related imports together
- Use explicit imports over wildcard imports

### File Structure & Naming
- **Main applications**: `access_to_cloud.py`, `sync_to_cloud.py`
- **Configuration**: `config.json` (public), `encrypted_credentials.bin` (private)
- **Utilities**: `encrypt_credentials.py`, `test_cloud_db.py`
- **Batch scripts**: `run_*.bat`, `compile_*.bat`
- **Database scripts**: `create_access_table.sql`

### Constants & Configuration
- Use uppercase for constants: `CONFIG_FILE`, `ENCRYPTED_CREDENTIALS_FILE`
- Configuration files use JSON format with camelCase keys
- Fixed encryption key: `b'XZgpn7Se8pQeHY8RMyeYf6e5Twq9PdOBVo9JPsqHZA4='`

### Error Handling Patterns
- Always wrap file operations in try-except blocks
- Use specific exception types (FileNotFoundError, json.JSONDecodeError)
- Provide meaningful error messages with context
- Include fallback default configurations
- Log errors to appropriate log files

### Function Documentation
- Use triple-quoted docstrings for all functions
- Brief description of purpose and behavior
- Include parameter descriptions if complex
- Example:
```python
def load_config():
    """Load public configuration from JSON file"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # Create default config if file doesn't exist
        return default_config
```

### Database Connection Patterns
- Use PyMySQL for MySQL connections (PyInstaller compatible)
- Use pyodbc for MS Access connections
- Always close connections in finally blocks or use context managers
- Connection timeout: 60 seconds for production, 10 seconds for testing
- Include connection error handling with specific error codes

### Security Implementation
- Never hardcode credentials in source code
- Use Fernet symmetric encryption for credential storage
- Separate public config from private encrypted credentials
- Fixed encryption key must match between encryption script and applications
- Validate credential file existence and format

### Logging & Output
- Use print() for user-facing messages and status updates
- Log detailed errors to log files in `logs/` directory
- Include timestamps in log entries
- Use structured log messages for debugging

### Batch Processing
- Process records in configurable batch sizes (default: 100)
- Track sync position using timestamp files
- Implement robust error recovery for partial batch failures
- Use transaction boundaries for database operations

### Scheduled Operations
- Support configurable sync times in HH:MM format
- Use continuous running with sleep intervals
- Check current time against scheduled times array
- Implement graceful shutdown handling

### Windows-Specific Considerations
- Use double backslashes for file paths in JSON
- Account for Windows path length limitations
- Use Windows Services (NSSM) for production deployment
- Handle Windows-specific file locking issues

### PyInstaller Compatibility
- Use PyMySQL instead of mysql-connector-python
- Avoid dynamic imports that may break compilation
- Test compiled executables thoroughly
- Include all required data files in distribution

### Code Comments
- Keep comments concise and relevant
- Explain complex business logic
- Document security-critical operations
- Include setup instructions in README

## Development Workflow

1. **Feature Development**: Create/modify Python files following style guidelines
2. **Configuration**: Update `config.json` for public settings, use `encrypt_credentials.py` for private data
3. **Testing**: Use `test_cloud_db.py` for connectivity, manual testing for sync operations
4. **Building**: Use `compile_for_nssm.bat` to create production executables
5. **Deployment**: Distribute executable + config files + encrypted credentials

## Security Notes

- Never commit actual credentials to version control
- The encryption key is hardcoded but embedded in compiled executables
- Only authorized personnel should have access to `encrypt_credentials.py`
- Validate all external inputs and file paths
- Use secure database connections with proper timeouts

## Common Pitfalls to Avoid

- Don't use mysql-connector-python (not PyInstaller compatible)
- Don't hardcode file paths - use configuration
- Don't ignore exception handling for file operations
- Don't forget to close database connections
- Don't modify the fixed encryption key without updating all components