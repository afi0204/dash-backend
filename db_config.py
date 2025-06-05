import os

DB_CONFIG = {
    'driver': '{ODBC Driver 17 for SQL Server}',
    'server': os.getenv('DB_SERVER', '196.190.251.194'),  # default to correct IP if env not set
    'database': os.getenv('DB_NAME', 'WaterMeter2'),
    'uid': os.getenv('DB_USER', 'sa'),
    'pwd': os.getenv('DB_PASS', 'DAFTech@2024'),
    'encrypt': 'yes',
    'trust_server_certificate': 'yes',
}

def get_db_connection_string():
    return (
        f"DRIVER={DB_CONFIG['driver']};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['uid']};"
        f"PWD={DB_CONFIG['pwd']};"
        f"Encrypt={DB_CONFIG['encrypt']};"
        f"TrustServerCertificate={DB_CONFIG['trust_server_certificate']};"
    )
