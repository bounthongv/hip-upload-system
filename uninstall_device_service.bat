@echo off
echo Uninstalling HIP Device Server Service...
echo Please run this as Administrator!

REM Stop the service first
net stop HIPDeviceServer

REM Uninstall the service
"D:\hipupload\venv\Scripts\python.exe" "D:\hipupload\device_server_srv.py" remove

if %ERRORLEVEL% EQU 0 (
    echo Service uninstalled successfully!
) else (
    echo Failed to uninstall service. Make sure you're running as Administrator.
)

pause