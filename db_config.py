# db_config.py
DB_CONFIG = {
    'driver': 'ODBC Driver 17 for SQL Server', # Or whatever correct driver name you're using
    'server': '196.190.251.194,1433', # <-- Add the port here
    'database': 'WaterMeter2',
    'uid': 'sa',
    'pwd': 'DAFTech@2024', 
    'encrypt': 'yes',
    'trust_server_certificate': 'yes'
}

def get_db_connection_string():
    conn_str_parts = [
        f"DRIVER={DB_CONFIG['driver']}",
        f"SERVER={DB_CONFIG['server']}", # Server now includes port
        f"DATABASE={DB_CONFIG['database']}",
        f"UID={DB_CONFIG['uid']}",
        f"PWD={DB_CONFIG['pwd']}",
    ]
    if DB_CONFIG.get('encrypt', 'yes').lower() == 'yes': # Default to yes if not specified or invalid
        conn_str_parts.append("Encrypt=yes")
    if DB_CONFIG.get('trust_server_certificate', 'yes').lower() == 'yes': # Default to yes
        conn_str_parts.append("TrustServerCertificate=yes")
    
    # Optional: Add connection timeout
    conn_str_parts.append("Timeout=30") # Example: 30 second timeout

    return ";".join(conn_str_parts) + ";" # Ensure trailing semicolon for some drivers