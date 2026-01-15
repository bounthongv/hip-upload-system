@echo off
echo Starting HIP Device Server Controller (System Tray)...
echo Note: This may need to run as Administrator to control the service.

"D:\hipupload\venv\Scripts\python.exe" "D:\hipupload\device_server_controller.py"

if %ERRORLEVEL% EQU 0 (
    echo Controller closed.
) else (
    echo Error running controller. Make sure all dependencies are installed.
)

pause