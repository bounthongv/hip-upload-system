"""
HIP Hybrid Sync Service
Monitors the MS Access database (populated by HIP Premium Time) and syncs to Cloud MySQL.
"""
import os
import sys
import time
import json
from datetime import datetime
from access_sync_manager_pure import PureAccessSyncManager

# Use the specific config file
CONFIG_FILE = "hybrid_config.json"

def main():
    print("=" * 60)
    print("HIP Hybrid Sync Service")
    print("Bridge between HIP Premium Time and Cloud Database")
    print("=" * 60)
    
    # Initialize manager
    manager = PureAccessSyncManager(config_file=CONFIG_FILE)
    
    # Verify DB path
    config = manager.load_config()
    db_path = config.get("ACCESS_DB_PATH", "")
    
    print(f"Monitoring Database: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"ERROR: Database file not found!")
        print(f"Please ensure HIP Premium Time is installed and the path is correct.")
        print("Waiting for file to appear...")
    else:
        print("Database found! Ready to sync.")
        
    print("-" * 60)
    print("Service running. Press Ctrl+C to stop.")
    
    try:
        while True:
            # Run sync cycle
            manager.run_sync_cycle()
            
            # Wait for next cycle (default 60 seconds)
            # We use a short cycle for "near realtime" feel
            time.sleep(30)
            
    except KeyboardInterrupt:
        print("\nService stopped by user.")
    except Exception as e:
        print(f"\nCritical Error: {e}")
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
