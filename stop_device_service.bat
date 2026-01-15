@echo off
echo Stopping HIP Device Server Service...
net stop HIPDeviceServer

if %ERRORLEVEL% EQU 0 (
    echo Service stopped successfully!
) else (
    echo Failed to stop service. Make sure it's installed and you're running as Administrator.
)

pause