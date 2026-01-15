@echo off
echo Uninstalling HIP Sync to Cloud Suite...

REM Check if running as administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo This script must be run as Administrator!
    echo Right-click on this file and select "Run as administrator"
    pause
    exit /b 1
)

echo.
echo Stopping HIP Sync Service...
net stop HIPSyncToCloud

echo.
echo Removing HIP Sync Service...
"dist\hip_sync_service.exe" remove

if %errorlevel% equ 0 (
    echo Service removed successfully!
    echo.
    echo Uninstallation complete!
) else (
    echo Service removal may have failed.
    echo Please check if the service still exists in Windows Services.
)

echo.
pause