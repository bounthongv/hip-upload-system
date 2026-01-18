"""
System Tray Application for HIP Text Log to Cloud Sync
Refactored to use SyncLogManager and provide live logs.
"""
import sys
import os
import ctypes
import time
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QMessageBox,
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QGroupBox, QFormLayout, QLineEdit, QLabel, QFileDialog
)
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import QTimer, QThread, pyqtSignal

# Import the shared manager logic
try:
    from sync_log_manager import SyncLogManager
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from sync_log_manager import SyncLogManager

class SyncWorker(QThread):
    """Worker thread that runs the sync manager"""
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.paused = False
        self.manager = SyncLogManager(logger_callback=self._log_wrapper)
    
    def _log_wrapper(self, message):
        self.log_signal.emit(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def run(self):
        self.running = True
        last_run_minute = None
        self.log_signal.emit("Worker thread started. Waiting for schedule...")

        while self.running:
            if not self.paused:
                config = self.manager.load_config()
                upload_times = config.get("UPLOAD_TIMES", ["09:00", "12:00", "17:00", "22:00"])
                
                now = datetime.now()
                current_time = now.strftime("%H:%M")

                if current_time in upload_times:
                    if current_time != last_run_minute:
                        self.status_signal.emit(f"Syncing ({current_time})...")
                        self.manager.paused = False
                        self.manager.run_sync_cycle()
                        last_run_minute = current_time
                        self.status_signal.emit("Idle")
            
            for _ in range(30):
                if not self.running: break
                time.sleep(1)

    def stop(self):
        self.running = False
        self.manager.paused = True
    
    def pause(self):
        self.paused = True
        self.manager.paused = True
        self.status_signal.emit("Paused")

    def resume(self):
        self.paused = False
        self.manager.paused = False
        self.status_signal.emit("Idle")

class ConfigDialog(QDialog):
    """Dialog for editing configuration"""
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.setWindowTitle("Configuration Editor")
        self.setGeometry(300, 300, 500, 250)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        form_group = QGroupBox("Sync Configuration")
        form_layout = QFormLayout()

        config = self.manager.load_config()
        defaults = self.manager._get_default_config()

        # Log Directory Selection
        self.log_dir_layout = QHBoxLayout()
        self.log_dir_edit = QLineEdit()
        self.log_dir_edit.setText(config.get("LOG_DIR", defaults["LOG_DIR"]))
        self.browse_btn = QPushButton("...")
        self.browse_btn.setFixedWidth(30)
        self.browse_btn.clicked.connect(self.browse_folder)
        
        self.log_dir_layout.addWidget(self.log_dir_edit)
        self.log_dir_layout.addWidget(self.browse_btn)
        
        form_layout.addRow("Log Directory:", self.log_dir_layout)

        # Times
        self.times_edit = QLineEdit()
        self.times_edit.setText(", ".join(config.get("UPLOAD_TIMES", defaults["UPLOAD_TIMES"])))
        form_layout.addRow("Upload Times (HH:MM):", self.times_edit)

        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_config)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Log Directory", self.log_dir_edit.text())
        if folder:
            self.log_dir_edit.setText(folder.replace('/', '\\'))

    def save_config(self):
        try:
            times_str = self.times_edit.text()
            if not times_str.strip():
                raise ValueError("Upload times cannot be empty")

            upload_times = [t.strip() for t in times_str.split(",")]
            for t in upload_times:
                if len(t) != 5 or t[2] != ':' :
                    raise ValueError(f"Invalid format: {t}. Use HH:MM")

            config = self.manager.load_config()
            config["LOG_DIR"] = self.log_dir_edit.text()
            config["UPLOAD_TIMES"] = upload_times
            
            if self.manager.save_config(config):
                QMessageBox.information(self, "Success", "Configuration saved!")
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Failed to write config file.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

class LogViewer(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Live Log Viewer")
        self.setGeometry(300, 300, 700, 500)
        layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("font-family: Consolas, Monospace; font-size: 10pt;")
        
        layout.addWidget(self.log_text)
        
        close_btn = QPushButton("Close (Keep Running)")
        close_btn.clicked.connect(self.hide)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)

    def append_log(self, message):
        self.log_text.append(message)
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def closeEvent(self, event):
        event.ignore()
        self.hide()

class SystemTrayApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        self.worker = SyncWorker()
        
        self.log_viewer = LogViewer()
        self.worker.log_signal.connect(self.log_viewer.append_log)
        self.worker.status_signal.connect(self.update_tray_status)

        self.setup_tray()
        
        self.worker.start()
        self.update_tray_status("Idle")

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon()
        
        if os.path.exists("upload.ico"):
            icon = QIcon("upload.ico")
        else:
            pixmap = QPixmap(32, 32)
            pixmap.fill()
            icon = QIcon(pixmap)
        self.tray_icon.setIcon(icon)

        self.menu = QMenu()
        
        self.status_action = self.menu.addAction("Status: Starting...")
        self.status_action.setEnabled(False)
        self.menu.addSeparator()

        self.start_action = self.menu.addAction("Start / Resume")
        self.start_action.triggered.connect(self.worker.resume)
        
        self.pause_action = self.menu.addAction("Pause")
        self.pause_action.triggered.connect(self.worker.pause)
        
        self.menu.addSeparator()
        
        self.config_action = self.menu.addAction("Configure")
        self.config_action.triggered.connect(self.open_config)

        self.logs_action = self.menu.addAction("View Live Logs")
        self.logs_action.triggered.connect(self.log_viewer.show)

        self.menu.addSeparator()
        
        self.exit_action = self.menu.addAction("Exit")
        self.exit_action.triggered.connect(self.exit_app)

        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.on_tray_click)

    def on_tray_click(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.log_viewer.show()

    def update_tray_status(self, status):
        self.status_action.setText(f"Status: {status}")

    def open_config(self):
        dialog = ConfigDialog(self.worker.manager)
        dialog.exec_()

    def exit_app(self):
        self.worker.stop()
        self.worker.wait(2000)
        self.app.quit()

    def run(self):
        return self.app.exec_()

def main():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        return
    
    app = SystemTrayApp()
    sys.exit(app.run())

if __name__ == "__main__":
    main()
