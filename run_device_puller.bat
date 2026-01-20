@echo off
echo ============================================
echo HIP CMI F68S Device Puller
echo TCP Direct Connection
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

echo.
echo Options:
echo   1. Test device connection
echo   2. Pull once from all devices  
echo   3. Run scheduled pulls
echo   4. Exit
echo.

set /p choice="Enter choice (1-4): "

if "%choice%"=="1" (
    set /p ip="Enter device IP: "
    set /p port="Enter port [4370]: "
    if "%port%"=="" set port=4370
    python hip_device_puller.py test %ip% %port%
) else if "%choice%"=="2" (
    python hip_device_puller.py once
) else if "%choice%"=="3" (
    python hip_device_puller.py scheduled
) else if "%choice%"=="4" (
    echo Goodbye!
    exit /b 0
) else (
    echo Invalid choice
)

pause
