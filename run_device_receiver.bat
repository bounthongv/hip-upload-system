@echo off
echo ============================================
echo HIP CMI F68S Device Receiver
echo HTTP 1.0 ADMS Server
echo ============================================
echo.

cd /d "%~dp0"

REM Check if Python is available
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python 3.x first
    pause
    exit /b 1
)

REM Check if venv exists
if exist "venv\Scripts\python.exe" (
    echo Using virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo Using system Python...
)

echo Starting Device Receiver Server...
echo.
python hip_device_receiver.py

pause
