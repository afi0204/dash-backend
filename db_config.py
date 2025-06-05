# db_config.py
DB_CONFIG = {
    'driver': '{ODBC Driver 17 for SQL Server}', # Or other appropriate driver
    'server': '196.190.251.194',
    'database': 'WaterMeter2',
    'uid': 'sa',
    'pwd': 'DAFTech@2024',
    'encrypt': 'yes',  # Recommended if server supports it
    'trust_server_certificate': 'yes' # For self-signed certs or if not using encryption properly; be cautious in prod
}

def get_db_connection_string():
    return (
        f"DRIVER={DB_CONFIG['driver']};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['uid']};"
        f"PWD={DB_CONFIG['pwd']};"
        # Add these if you have issues connecting, especially with Azure SQL or newer SQL Server versions
        # f"Encrypt={DB_CONFIG.get('encrypt', 'yes')};"
        # f"TrustServerCertificate={DB_CONFIG.get('trust_server_certificate', 'yes')};"
        # f"Connection Timeout=30;"
    )