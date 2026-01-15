import sys
import subprocess
import win32serviceutil
import win32service
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
import os
import tempfile

class ServiceController:
    """Controls the Windows service"""
    
    @staticmethod
    def start_service():
        try:
            win32serviceutil.StartService("HIPDeviceServer")
            return True, "Service started successfully"
        except Exception as e:
            return False, f"Failed to start service: {str(e)}"
    
    @staticmethod
    def stop_service():
        try:
            win32serviceutil.StopService("HIPDeviceServer")
            return True, "Service stopped successfully"
        except Exception as e:
            return False, f"Failed to stop service: {str(e)}"
    
    @staticmethod
    def restart_service():
        try:
            win32serviceutil.RestartService("HIPDeviceServer")
            return True, "Service restarted successfully"
        except Exception as e:
            return False, f"Failed to restart service: {str(e)}"
    
    @staticmethod
    def service_status():
        try:
            status = win32serviceutil.QueryServiceStatus("HIPDeviceServer")[1]
            status_map = {
                win32service.SERVICE_STOPPED: "Stopped",
                win32service.SERVICE_START_PENDING: "Starting...",
                win32service.SERVICE_STOP_PENDING: "Stopping...",
                win32service.SERVICE_RUNNING: "Running",
                win32service.SERVICE_CONTINUE_PENDING: "Continuing...",
                win32service.SERVICE_PAUSE_PENDING: "Pausing...",
                win32service.SERVICE_PAUSED: "Paused"
            }
            return status_map.get(status, "Unknown")
        except:
            return "Not Installed"

class ServiceMonitorThread(QThread):
    """Monitors service status and emits signals when it changes"""
    status_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.running = True
        
    def run(self):
        last_status = ""
        while self.running:
            current_status = ServiceController.service_status()
            if current_status != last_status:
                self.status_changed.emit(current_status)
                last_status = current_status
            self.msleep(2000)  # Check every 2 seconds
    
    def stop(self):
        self.running = False

class SystemTrayApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        # Create tray icon
        self.tray_icon = QSystemTrayIcon()
        
        # Use a standard system icon for the tray
        from PyQt5.QtWidgets import QStyle
        icon = self.app.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        
        # Create menu
        self.tray_menu = QMenu()
        
        # Status label (will be updated dynamically)
        self.status_action = self.tray_menu.addAction("Status: Unknown")
        self.status_action.setEnabled(False)
        self.tray_menu.addSeparator()
        
        # Control actions
        self.start_action = self.tray_menu.addAction("Start Service")
        self.start_action.triggered.connect(self.start_service)
        
        self.stop_action = self.tray_menu.addAction("Stop Service")
        self.stop_action.triggered.connect(self.stop_service)
        
        self.restart_action = self.tray_menu.addAction("Restart Service")
        self.restart_action.triggered.connect(self.restart_service)
        
        self.status_action_menu = self.tray_menu.addAction("Check Status")
        self.status_action_menu.triggered.connect(self.check_status)
        
        self.tray_menu.addSeparator()
        
        self.about_action = self.tray_menu.addAction("About")
        self.about_action.triggered.connect(self.show_about)
        
        self.tray_menu.addSeparator()
        
        self.exit_action = self.tray_menu.addAction("Exit")
        self.exit_action.triggered.connect(self.exit_app)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        
        # Set up status monitoring
        self.monitor_thread = ServiceMonitorThread()
        self.monitor_thread.status_changed.connect(self.update_status)
        self.monitor_thread.start()
        
        # Show the tray icon
        self.tray_icon.show()
        
    def on_tray_icon_activated(self, reason):
        """Handle tray icon clicks"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.check_status()
    
    def update_status(self, status):
        """Update the status in the menu"""
        self.status_action.setText(f"Status: {status}")
        
        # Update icon based on status
        if status == "Running":
            # For a real implementation, you'd use a green icon
            pass
        elif status == "Stopped":
            # For a real implementation, you'd use a red icon
            pass
    
    def start_service(self):
        success, message = ServiceController.start_service()
        self.show_message("Start Service", message, success)
    
    def stop_service(self):
        success, message = ServiceController.stop_service()
        self.show_message("Stop Service", message, success)
    
    def restart_service(self):
        success, message = ServiceController.restart_service()
        self.show_message("Restart Service", message, success)
    
    def check_status(self):
        status = ServiceController.service_status()
        self.show_message("Service Status", f"Current status: {status}")
    
    def show_about(self):
        about_text = "APIS Co. Ltd\nAll rights reserved.\nJan 2026."
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("About HIP Device Server Controller")
        msg.setText(about_text)
        msg.exec_()
    
    def show_message(self, title, message, success=True):
        icon = QMessageBox.Information
        if not success:
            icon = QMessageBox.Warning
        msg = QMessageBox()
        msg.setIcon(icon)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.exec_()
    
    def exit_app(self):
        self.monitor_thread.stop()
        self.monitor_thread.wait()
        self.tray_icon.hide()
        self.app.quit()
    
    def run(self):
        return self.app.exec_()

def main():
    # Check if running as admin (required for service management)
    import ctypes
    if not ctypes.windll.shell32.IsUserAnAdmin():
        # Re-run the program with admin rights
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        return

    app = SystemTrayApp()
    sys.exit(app.run())

if __name__ == "__main__":
    main()