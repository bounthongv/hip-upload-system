@echo off
echo Compiling access_to_cloud.py to executable...

REM Make sure we're in the right directory
cd /d D:\hipupload

REM Compile the script using PyInstaller
"D:\hipupload\venv\Scripts\python.exe" -m PyInstaller --onefile --console --name=access_to_cloud_service access_to_cloud.py

echo.
echo Compilation completed!
echo.
echo To install as a service using NSSM:
echo 1. Download NSSM from https://nssm.cc/download
echo 2. Extract it to a folder (e.g., C:\nssm)
echo 3. Run Command Prompt as Administrator
echo 4. Execute: C:\nssm\nssm.exe install HIPAccessToCloud
echo 5. In the NSSM GUI:
echo    - Path: D:\hipupload\dist\access_to_cloud_service.exe
echo    - Startup directory: D:\hipupload
echo    - Arguments: (leave blank)
echo 6. Click Install service
echo.
echo The service will run continuously, checking for scheduled sync times.
echo Configuration is done via config.json and credentials.json files.
echo.
pause