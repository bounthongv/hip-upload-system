"""
System Tray Application for HIP Access to Cloud Sync
Provides a user-friendly interface with system tray controls
"""
import os
import sys
import json
import threading
import time
from datetime import datetime
import pyodbc
import pymysql
from cryptography.fernet import Fernet
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QGroupBox, QFormLayout
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
import subprocess
import ctypes

# Configuration files
CONFIG_FILE = "config.json"
ENCRYPTED_CREDENTIALS_FILE = "encrypted_credentials.bin"

def load_config():
    """Load public configuration from JSON file"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # Create default config if file doesn't exist
        default_config = {
            "ACCESS_DB_PATH": "D:\\\\Program Files (x86)\\\\HIPPremiumTime-2.0.4\\\\db\\\\Pm2014.mdb",
            "ACCESS_PASSWORD": "hippmforyou",
            "UPLOAD_TIMES": ["09:00", "12:00", "17:00", "22:00"],
            "LAST_SYNC_FILE": "last_sync_access.txt",
            "BATCH_SIZE": 100
        }
        save_config(default_config)
        return default_config
    except Exception as e:
        print(f"Error loading config: {e}")
        return {
            "ACCESS_DB_PATH": "D:\\\\Program Files (x86)\\\\HIPPremiumTime-2.0.4\\\\db\\\\Pm2014.mdb",
            "ACCESS_PASSWORD": "hippmforyou",
            "UPLOAD_TIMES": ["09:00", "12:00", "17:00", "22:00"],
            "LAST_SYNC_FILE": "last_sync_access.txt",
            "BATCH_SIZE": 100
        }

def load_encrypted_credentials():
    """Load and decrypt credentials from encrypted file"""
    try:
        # Fixed encryption key - this must match the key used in encrypt_credentials.py
        ENCRYPTION_KEY = b'XZgpn7Se8pQeHY8RMyeYf6e5Twq9PdOBVo9JPsqHZA4='
        
        with open(ENCRYPTED_CREDENTIALS_FILE, 'rb') as f:
            encrypted_data = f.read()
        
        fernet = Fernet(ENCRYPTION_KEY)
        decrypted_data = fernet.decrypt(encrypted_data)
        credentials = json.loads(decrypted_data.decode())
        return credentials.get("DB_CONFIG", {})
    except FileNotFoundError:
        print(f"Encrypted credentials file {ENCRYPTED_CREDENTIALS_FILE} not found!")
        return {}
    except Exception as e:
        print(f"Error decrypting credentials: {e}")
        return {}

def save_config(config):
    """Save public configuration to JSON file"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def log_msg(message):
    print(f"[{datetime.now()}] {message}")
    sys.stdout.flush()

class SyncWorker(QThread):
    """Worker thread for sync operations"""
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.paused = False
        self.credentials = load_encrypted_credentials()
    
    def run(self):
        self.running = True
        last_run_minute = None

        while self.running:
            if not self.paused:
                # Reload config periodically to pick up changes
                current_config = load_config()
                current_upload_times = current_config.get("UPLOAD_TIMES", ["09:00", "12:00", "17:00", "22:00"])

                now = datetime.now()
                current_time = now.strftime("%H:%M")

                # Check if current time matches schedule
                if current_time in current_upload_times:
                    if current_time != last_run_minute:
                        self.status_signal.emit(f"Scheduled time reached ({current_time}). Starting sync...")
                        self.sync_from_access_to_cloud()
                        last_run_minute = current_time
                    else:
                        self.log_signal.emit(f"DEBUG: Time {current_time} already processed in this minute, skipping")
                else:
                    self.log_signal.emit(f"DEBUG: Current time {current_time} not in schedule, continuing...")

            # Sleep for 30 seconds to spare CPU
            time.sleep(30)
    
    def stop(self):
        self.running = False
    
    def pause(self):
        self.paused = True
    
    def resume(self):
        self.paused = False
    
    def connect_to_access_db(self):
        """Connect to the MS Access database"""
        try:
            # Load config dynamically
            config = load_config()
            db_path = config.get("ACCESS_DB_PATH", "D:\\\\Program Files (x86)\\\\HIPPremiumTime-2.0.4\\\\db\\\\Pm2014.mdb")
            password = config.get("ACCESS_PASSWORD", "hippmforyou")

            # Connection string for MS Access database with password
            conn_str = (
                r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
                f"DBQ={db_path};"
                f"PWD={password}"
            )
            conn = pyodbc.connect(conn_str)
            return conn
        except Exception as e:
            self.log_signal.emit(f"Error connecting to Access database: {e}")
            return None

    def connect_to_mysql_db(self):
        """Connect to the MySQL cloud database"""
        try:
            # Load credentials dynamically
            current_credentials = load_encrypted_credentials()

            conn = pymysql.connect(
                host=current_credentials.get('host', 'localhost'),
                user=current_credentials.get('user', ''),
                password=current_credentials.get('password', ''),
                database=current_credentials.get('database', ''),
                port=current_credentials.get('port', 3306),
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=60,
                read_timeout=60,
                write_timeout=60
            )
            return conn
        except Exception as e:
            self.log_signal.emit(f"Error connecting to MySQL database: {e}")
            return None

    def check_table_exists(self):
        """Check if the target table exists in MySQL database"""
        mysql_conn = self.connect_to_mysql_db()
        if not mysql_conn:
            return False
        
        try:
            cursor = mysql_conn.cursor()
            cursor.execute("SELECT 1 FROM access_device_logs LIMIT 1")
            cursor.fetchone()
            mysql_conn.close()
            return True
        except:
            mysql_conn.close()
            return False

    def get_last_sync_position(self):
        """Get the last sync position (timestamp and SN) from file"""
        try:
            with open(load_config().get("LAST_SYNC_FILE", "last_sync_access.txt"), 'r') as f:
                content = f.read().strip()
                if '|' in content:
                    timestamp_part, sn_part = content.rsplit('|', 1)
                    return timestamp_part, sn_part
                else:
                    return content, None
        except FileNotFoundError:
            return None, None

    def set_last_sync_position(self, timestamp, sn):
        """Save the last sync position (timestamp and SN) to file"""
        with open(load_config().get("LAST_SYNC_FILE", "last_sync_access.txt"), 'w') as f:
            f.write(f"{timestamp}|{sn}")

    def get_new_records_from_access(self, last_timestamp=None, last_sn=None, limit=None):
        """Get new records from the checkinout table since last sync position"""
        conn = self.connect_to_access_db()
        if not conn:
            return []

        try:
            cursor = conn.cursor()

            if last_timestamp:
                if last_sn:
                    # Get records newer than last sync position (timestamp + SN)
                    query = """
                    SELECT Badgenumber, checktime, checktype, verifycode, sensorid, workcode, sn
                    FROM checkinout
                    WHERE (checktime > ?) OR (checktime = ? AND sn > ?)
                    ORDER BY checktime, sn
                    """
                    cursor.execute(query, (last_timestamp, last_timestamp, last_sn))
                else:
                    # Get records newer than last timestamp only
                    query = """
                    SELECT Badgenumber, checktime, checktype, verifycode, sensorid, workcode, sn
                    FROM checkinout
                    WHERE checktime > ?
                    ORDER BY checktime, sn
                    """
                    cursor.execute(query, (last_timestamp,))
            else:
                # Get all records (first sync)
                query = """
                SELECT Badgenumber, checktime, checktype, verifycode, sensorid, workcode, sn
                FROM checkinout
                ORDER BY checktime, sn
                """
                cursor.execute(query)

            if limit:
                # Limit the results
                records = []
                for i, row in enumerate(cursor.fetchall()):
                    if i >= limit:
                        break
                    records.append(row)
            else:
                records = cursor.fetchall()

            conn.close()
            return records
        except Exception as e:
            self.log_signal.emit(f"Error querying Access database: {e}")
            if conn:
                conn.close()
            return []

    def sync_records_to_cloud(self, access_records):
        """Sync records from Access to MySQL cloud database"""
        if not access_records:
            return 0

        # Check if target table exists
        if not self.check_table_exists():
            self.log_signal.emit("ERROR: access_device_logs table does not exist in MySQL database!")
            self.log_signal.emit("Please create the table using create_access_table.sql before running sync.")
            return 0

        mysql_conn = self.connect_to_mysql_db()
        if not mysql_conn:
            return 0

        try:
            cursor = mysql_conn.cursor()

            # Prepare INSERT statement for the new access_device_logs table
            insert_query = """
            INSERT IGNORE INTO access_device_logs
            (badge_number, check_time, check_type, verify_code, sensor_id, work_code, device_sn, raw_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """

            count = 0
            for record in access_records:
                # Extract Access fields
                badgenumber = record[0]  # Badgenumber
                checktime = record[1]    # checktime
                checktype = record[2]    # checktype
                verifycode = record[3]   # verifycode
                sensorid = record[4]     # sensorid
                workcode = record[5]     # workcode
                sn = record[6]           # sn

                # Format raw data string
                raw_data = f"Badge:{badgenumber}|CheckTime:{checktime}|Type:{checktype}|Verify:{verifycode}|Sensor:{sensorid}|WorkCode:{workcode}|SN:{sn}"

                # Map to MySQL fields
                values = (
                    str(badgenumber) if badgenumber else '',  # badge_number
                    str(checktime) if checktime else None,    # check_time
                    str(checktype) if checktype else '',      # check_type
                    str(verifycode) if verifycode else '',    # verify_code
                    str(sensorid) if sensorid else '',        # sensor_id
                    str(workcode) if workcode else '',        # work_code
                    str(sn) if sn else 'HIP_ACCESS_DB',       # device_sn
                    raw_data                                   # raw_data
                )

                cursor.execute(insert_query, values)
                count += 1

            mysql_conn.commit()
            self.log_signal.emit(f"Uploaded {count} records to cloud database")
            return count

        except Exception as e:
            self.log_signal.emit(f"Error syncing to MySQL: {e}")
            return 0
        finally:
            try:
                if 'cursor' in locals():
                    cursor.close()
            except:
                pass
            try:
                if mysql_conn and mysql_conn.open:
                    mysql_conn.close()
            except:
                pass

    def sync_from_access_to_cloud(self):
        """Main sync function with batching and per-batch sync position updates"""
        self.log_signal.emit("Starting sync from MS Access to Cloud...")

        # Check if target table exists first
        if not self.check_table_exists():
            self.log_signal.emit("ERROR: access_device_logs table does not exist in MySQL database!")
            self.log_signal.emit("Please create the table using create_access_table.sql before running sync.")
            return 0

        # Get last sync position
        last_timestamp, last_sn = self.get_last_sync_position()

        # Get total count first
        all_records = self.get_new_records_from_access(last_timestamp, last_sn)
        total_records = len(all_records)

        if total_records == 0:
            self.log_signal.emit("No new records found in Access database")
            return 0

        # Get current config for batch size
        current_config = load_config()
        current_batch_size = current_config.get("BATCH_SIZE", 100)

        self.log_signal.emit(f"Found {total_records} new records in Access database. Processing in batches of {current_batch_size}...")

        # Process in batches
        total_uploaded = 0
        for i in range(0, total_records, current_batch_size):
            batch = all_records[i:i + current_batch_size]
            batch_uploaded = self.sync_records_to_cloud(batch)
            total_uploaded += batch_uploaded

            self.log_signal.emit(f"Processed batch {i//current_batch_size + 1}: {batch_uploaded} records uploaded")

            # Update last sync position after each batch with the last record's position
            if batch:
                last_record = batch[-1]  # Get the last record in this batch
                batch_last_timestamp = str(last_record[1])  # checktime is at index 1
                batch_last_sn = str(last_record[6]) if last_record[6] else 'UNKNOWN'  # sn is at index 6
                self.set_last_sync_position(batch_last_timestamp, batch_last_sn)
                self.log_signal.emit(f"Updated sync position to: {batch_last_timestamp}|{batch_last_sn}")

            # Small delay between batches to avoid overwhelming the database
            time.sleep(0.1)

        self.log_signal.emit(f"Sync completed. Total uploaded: {total_uploaded} records.")
        return total_uploaded

class ConfigDialog(QDialog):
    """Dialog for editing configuration"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Configuration Editor")
        self.setGeometry(300, 300, 500, 300)

        layout = QVBoxLayout()

        # Create form layout for configuration
        form_group = QGroupBox("Sync Configuration")
        form_layout = QFormLayout()

        # Load current config
        config = load_config()

        # Access DB Path
        self.db_path_edit = QLineEdit()
        self.db_path_edit.setText(config.get("ACCESS_DB_PATH", "D:\\\\Program Files (x86)\\\\HIPPremiumTime-2.0.4\\\\db\\\\Pm2014.mdb"))
        form_layout.addRow("Access DB Path:", self.db_path_edit)

        # Upload Times
        self.times_edit = QLineEdit()
        self.times_edit.setText(", ".join(config.get("UPLOAD_TIMES", ["09:00", "12:00", "17:00", "22:00"])))
        form_layout.addRow("Upload Times (HH:MM, comma separated):", self.times_edit)

        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        # Buttons
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Configuration")
        self.save_btn.clicked.connect(self.save_config)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def save_config(self):
        """Save configuration from the dialog"""
        try:
            # Parse upload times
            times_str = self.times_edit.text()
            if not times_str.strip():
                raise ValueError("Upload times cannot be empty")

            upload_times = [time.strip() for time in times_str.split(",")]

            # Validate time format
            for time_str in upload_times:
                if len(time_str) != 5 or time_str[2] != ':':
                    raise ValueError(f"Invalid time format: {time_str}. Use HH:MM format.")
                hour, minute = time_str.split(':')
                if not (hour.isdigit() and minute.isdigit()):
                    raise ValueError(f"Invalid time format: {time_str}. Use HH:MM format.")
                h, m = int(hour), int(minute)
                if h < 0 or h > 23 or m < 0 or m > 59:
                    raise ValueError(f"Invalid time: {time_str}. Hour must be 0-23, minute must be 0-59.")

            # Load existing config to preserve other fields
            config = load_config()

            # Update only the fields we're editing
            config["ACCESS_DB_PATH"] = self.db_path_edit.text()
            config["UPLOAD_TIMES"] = upload_times

            # Save to file
            save_config(config)

            QMessageBox.information(self, "Success", "Configuration saved successfully!")
            self.accept()

        except ValueError as e:
            QMessageBox.critical(self, "Error", f"Invalid configuration: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save configuration: {str(e)}")

class LogViewer(QDialog):
    """Dialog for viewing logs"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log Viewer")
        self.setGeometry(300, 300, 700, 500)
        
        layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        layout.addWidget(self.close_btn)
        
        self.setLayout(layout)
        
        # Connect to worker's log signal
        if hasattr(parent, 'worker'):
            parent.worker.log_signal.connect(self.append_log)
    
    def append_log(self, message):
        """Append message to log viewer"""
        self.log_text.append(message)
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

class SystemTrayApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        # Create tray icon
        self.tray_icon = QSystemTrayIcon()
        
        # Create a simple icon (in a real app, you'd use a proper icon file)
        pixmap = QPixmap(32, 32)
        pixmap.fill()
        icon = QIcon(pixmap)
        self.tray_icon.setIcon(icon)
        
        # Create menu
        self.tray_menu = QMenu()
        
        # Status label (will be updated dynamically)
        self.status_action = self.tray_menu.addAction("Status: Idle")
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
        
        self.config_action = self.tray_menu.addAction("Configure")
        self.config_action.triggered.connect(self.configure_settings)
        
        self.logs_action = self.tray_menu.addAction("View Logs")
        self.logs_action.triggered.connect(self.view_logs)
        
        self.tray_menu.addSeparator()
        
        self.about_action = self.tray_menu.addAction("About")
        self.about_action.triggered.connect(self.show_about)
        
        self.tray_menu.addSeparator()
        
        self.exit_action = self.tray_menu.addAction("Exit")
        self.exit_action.triggered.connect(self.exit_app)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        
        # Initialize worker thread
        self.worker = SyncWorker()
        self.worker.status_signal.connect(self.update_status)
        self.worker.log_signal.connect(self.log_message)
        
        # Show the tray icon
        self.tray_icon.show()
        
        # Start the worker thread
        self.worker.start()
    
    def on_tray_icon_activated(self, reason):
        """Handle tray icon clicks"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.check_status()
    
    def update_status(self, status):
        """Update the status in the menu"""
        self.status_action.setText(f"Status: {status}")
    
    def log_message(self, message):
        """Log message handler"""
        print(message)  # Also print to console
    
    def start_service(self):
        """Start the sync service"""
        self.worker.resume()
        self.update_status("Running")
        self.log_message(f"[{datetime.now()}] Service started")
    
    def stop_service(self):
        """Stop the sync service"""
        self.worker.pause()
        self.update_status("Stopped")
        self.log_message(f"[{datetime.now()}] Service stopped")
    
    def restart_service(self):
        """Restart the sync service"""
        self.worker.pause()
        self.worker.resume()
        self.update_status("Running")
        self.log_message(f"[{datetime.now()}] Service restarted")
    
    def check_status(self):
        """Check service status"""
        status = "Running" if not self.worker.paused else "Stopped"
        QMessageBox.information(None, "Service Status", f"Current status: {status}")
    
    def configure_settings(self):
        """Open configuration dialog"""
        try:
            dialog = ConfigDialog()
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Could not open configuration dialog: {str(e)}")

    def view_logs(self):
        """Open log viewer"""
        try:
            # Create a simple log viewer since the connection might not work properly
            log_dialog = QDialog()
            log_dialog.setWindowTitle("Log Viewer")
            log_dialog.setGeometry(300, 300, 700, 500)

            layout = QVBoxLayout()
            log_text = QTextEdit()
            log_text.setReadOnly(True)

            # Add some sample log content
            log_text.append("Log Viewer - Recent Messages:")
            log_text.append("No live logs available in this view")
            log_text.append("Check console output for real-time logs")

            layout.addWidget(log_text)

            close_btn = QPushButton("Close")
            close_btn.clicked.connect(log_dialog.close)
            layout.addWidget(close_btn)

            log_dialog.setLayout(layout)
            log_dialog.exec_()
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Could not open log viewer: {str(e)}")
    
    def show_about(self):
        """Show about dialog"""
        about_text = "HIP Access to Cloud Sync\nVersion 2.0\nAPIS Co. Ltd\nAll rights reserved.\nJan 2026."
        QMessageBox.about(None, "About", about_text)
    
    def exit_app(self):
        """Exit the application"""
        self.worker.stop()
        self.worker.wait()
        self.tray_icon.hide()
        self.app.quit()
    
    def run(self):
        return self.app.exec_()

def main():
    # Check if running as admin (required for service management)
    if not ctypes.windll.shell32.IsUserAnAdmin():
        # Re-run the program with admin rights
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        return

    app = SystemTrayApp()
    sys.exit(app.run())

if __name__ == "__main__":
    main()