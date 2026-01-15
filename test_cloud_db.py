import mysql.connector

# --- CONFIGURATION ---
config = {
    'user': 'apis_misuzu2',
    'password': 'Tw0NC35pu*',
    # CHANGE THIS LINE BELOW:
    'host': 'mysql.us.cloudlogin.co',
    'database': 'apis_misuzu2',
    'port': 3306,
    'raise_on_warnings': True,
    'connection_timeout': 10
}

print(f"Attempting to connect to {config['host']}...")

try:
    cnx = mysql.connector.connect(**config)
    print("\n✅ SUCCESS! Connection established.")
    print(f"Connected to database: {config['database']}")
    print(f"Server version: {cnx.get_server_info()}")
    cnx.close()

except mysql.connector.Error as err:
    print("\n❌ CONNECTION FAILED")
    print(f"Error Code: {err.errno}")
    print(f"Message: {err.msg}")
