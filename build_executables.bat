@echo off
echo Building HIP Upload System executables with PyInstaller...

REM Install PyInstaller if not already installed
"D:\hipupload\venv\Scripts\python.exe" -m pip install pyinstaller

echo Building Sync to Cloud Windows Service executable...
"D:\hipupload\venv\Scripts\pyinstaller.exe" "D:\hipupload\sync_to_cloud_service.spec"

echo Building Sync to Cloud System Tray Controller executable...
"D:\hipupload\venv\Scripts\pyinstaller.exe" "D:\hipupload\sync_to_cloud_controller.spec"

echo Building Device Server Windows Service executable...
"D:\hipupload\venv\Scripts\pyinstaller.exe" "D:\hipupload\device_server_service.spec"

echo Building Device Server System Tray Controller executable...
"D:\hipupload\venv\Scripts\pyinstaller.exe" "D:\hipupload\device_server_controller.spec"

echo Build process completed!
echo.
echo Sync to Cloud Service executable: dist\hip_sync_service.exe
echo Sync to Cloud Controller executable: dist\hip_sync_controller.exe
echo Device Server Service executable: dist\hip_device_service.exe
echo Device Server Controller executable: dist\hip_device_controller.exe
echo.
echo To install Sync to Cloud service: Run hip_sync_service.exe install as Administrator
echo To install Device Server service: Run hip_device_service.exe install as Administrator
echo To run controllers: Run hip_sync_controller.exe or hip_device_controller.exe
echo.
pause