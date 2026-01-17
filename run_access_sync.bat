@echo off
REM Activate virtual environment and run access_to_cloud.py
echo Starting HIP Access to Cloud Sync Service...

REM Change to the application directory
cd /d D:\hipupload

REM Activate the virtual environment
call venv\Scripts\activate.bat

REM Run the Python script
python access_to_cloud.py

echo Service stopped or encountered an error.
pause