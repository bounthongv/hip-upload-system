@echo off
echo Building HIP Sync to Cloud executables with PyInstaller...

REM Install PyInstaller if not already installed
"D:\hipupload\venv\Scripts\python.exe" -m pip install pyinstaller

echo Building Windows Service executable...
"D:\hipupload\venv\Scripts\pyinstaller.exe" "D:\hipupload\sync_to_cloud_service.spec"

echo Building System Tray Controller executable...
"D:\hipupload\venv\Scripts\pyinstaller.exe" "D:\hipupload\sync_to_cloud_controller.spec"

echo Build process completed!
echo.
echo Windows Service executable: dist\hip_sync_service.exe
echo System Tray Controller executable: dist\hip_sync_controller.exe
echo.
echo To install the service: Run hip_sync_service.exe install as Administrator
echo To run the controller: Run hip_sync_controller.exe
echo.
pause