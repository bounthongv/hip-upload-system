@echo off
echo Installing HIP Sync to Cloud Suite...

REM Check if running as administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo This script must be run as Administrator!
    echo Right-click on this file and select "Run as administrator"
    pause
    exit /b 1
)

echo.
echo Installing HIP Sync Service...
REM Install the service
"dist\hip_sync_service.exe" install

if %errorlevel% equ 0 (
    echo Service installed successfully!
    
    echo Starting the service...
    net start HIPSyncToCloud
    
    if %errorlevel% equ 0 (
        echo Service started successfully!
        echo.
        echo Installation complete!
        echo The HIP Sync to Cloud service is now running in the background.
        echo Run hip_sync_controller.exe to manage the service via system tray.
    ) else (
        echo Failed to start the service.
    )
) else (
    echo Failed to install the service.
)

echo.
pause