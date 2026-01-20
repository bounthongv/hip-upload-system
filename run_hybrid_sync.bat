@echo off
title HIP Cloud Sync Service
echo ========================================================
echo HIP Hybrid Cloud Sync
echo ========================================================
echo.
echo 1. Ensure HIP Premium Time software is running
echo 2. Ensure device is connected to HIP software
echo 3. This service will upload new data to the cloud
echo.

cd /d "%~dp0"

REM Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    pause
    exit
)

REM Use venv if available
if exist "venv\Scripts\python.exe" (
    echo Starting in Virtual Environment...
    venv\Scripts\python.exe hip_hybrid_service.py
) else (
    echo Starting with System Python...
    python hip_hybrid_service.py
)

if errorlevel 1 pause
