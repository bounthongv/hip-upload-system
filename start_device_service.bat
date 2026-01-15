@echo off
echo Starting HIP Device Server Service...
net start HIPDeviceServer

if %ERRORLEVEL% EQU 0 (
    echo Service started successfully!
) else (
    echo Failed to start service. Make sure it's installed and you're running as Administrator.
)

pause