@echo off
REM Activate virtual environment and run access_to_cloud.py
echo Starting HIP Access to Cloud Sync Service...

REM Change to the application directory
cd /d D:\hipupload

REM Create logs directory if it doesn't exist
if not exist logs mkdir logs

REM Activate the virtual environment
call venv\Scripts\activate.bat

REM Run the Python script and log output
python access_to_cloud.py >> logs\access_sync_output.log 2>&1

echo Service stopped or encountered an error. Check logs\access_sync_output.log
pause
