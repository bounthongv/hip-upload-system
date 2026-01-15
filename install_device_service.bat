@echo off
echo Installing HIP Device Server Service...
echo Please run this as Administrator!

REM Install the service
"D:\hipupload\venv\Scripts\python.exe" "D:\hipupload\device_server_srv.py" install

if %ERRORLEVEL% EQU 0 (
    echo Service installed successfully!
    echo You can now start the service with: net start HIPDeviceServer
) else (
    echo Failed to install service. Make sure you're running as Administrator.
)

pause