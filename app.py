# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import pyodbc
import datetime
import re
import logging # Import the logging module
import os # If using environment variables
from logging.handlers import RotatingFileHandler # Optional: for logging to a file
from functools import wraps
from dotenv import load_dotenv
 
from db_config import get_db_connection_string

# Load environment variables from .env file
load_dotenv() 

# --- Setup Logging ---
# Basic configuration (logs to console by default with Flask)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(name)s %(module)s %(funcName)s: %(message)s')

# Get a logger instance for your application
logger = logging.getLogger(__name__) # Use this logger for application-specific logs
                                     # Flask's app.logger can also be used

# Load API_KEY from environment variable for better security
# Set this environment variable where your app runs
API_KEY = os.environ.get("WATER_METER_API_KEY")
if not API_KEY: # Check if the environment variable was successfully loaded
    logger.critical("CRITICAL: WATER_METER_API_KEY environment variable not set!")
    # For a production app, you might want to exit or raise an exception here
    # For now, we'll let it proceed, but API calls requiring a key will fail if it's not set.
    # Consider setting a default or raising an error:
    raise ValueError("CRITICAL: WATER_METER_API_KEY environment variable not set!") # Uncommented to enforce key presence

# Using Flask's built-in app.logger is often convenient as it's already configured.
# You can also use logging.getLogger(__name__) if you prefer more separation.
# For this example, we'll enhance Flask's default logger.

# Optional: Configure logging to a file with rotation
# file_handler = RotatingFileHandler('water_meter_api.log', maxBytes=102400, backupCount=10) # 100KB per file
# file_handler.setFormatter(logging.Formatter(
#     '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
# ))
# file_handler.setLevel(logging.INFO)

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests (for development)

# --- Database Helper ---
def get_db_cursor():
    conn_str = get_db_connection_string()
    conn = pyodbc.connect(conn_str)
    return conn, conn.cursor()

# Add file handler to Flask's logger if configured
# if 'file_handler' in locals():
#     app.logger.addHandler(file_handler)
# Ensure Flask's logger level is set (if you use app.logger extensively)
# logger.setLevel(logging.INFO) # If using the custom logger instance primarily

# --- API Key Decorator ---
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.headers.get('X-API-KEY') == API_KEY:
            return f(*args, **kwargs)
        else:
            logger.warning("Unauthorized API access attempt.") # Use custom logger or app.logger
            return jsonify({"message": "ERROR: Unauthorized"}), 401
    return decorated_function

# --- SMS Parsing Logic ---
def parse_sms_data(sms_string):
    """
    Parses SMS string like: #S,0010714529,@,3387,76,16557
    Returns a dictionary or None if parsing fails.
    """
    # Regex to capture the groups, making it a bit more robust to extra spaces
    # Group 1: Start characters (e.g., #S)
    # Group 2: Meter ID
    # Group 3: Separator/Status (e.g., @)
    # Group 4: Battery Voltage
    # Group 5: Network Signal
    # Group 6: Liters
    match = re.match(r"^\s*([^,]+)\s*,\s*(\w+)\s*,\s*([^,]+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*$", sms_string)
    if match:
        start_char, mid, separator_char, battery, network, liters = match.groups()

        parsed = {
            "MID": mid,
            "battery_vol": battery, # e.g., "3387" (mV)
            "network": network,     # e.g., "76"
            "WH": liters        # e.g., "16557"
        }

        # Derive status_code based on format and data values
        status_code = "OK" # Default
        if start_char != "#S" or separator_char != "@":
            status_code = "FORMAT_WARN" # Or some other indicator
        else:
            try:
                battery_val_mv = int(battery)
                network_val = int(network)
                if battery_val_mv < 3500: # Example: 3.5V
                    status_code = "LOW_BATT"
                elif network_val < 10: # Example: very low signal
                    status_code = "NO_SIGNAL"
            except ValueError:
                status_code = "DATA_ERR" # If battery/network aren't numbers

        parsed["status_code"] = status_code
        return parsed
    logger.warning(f"Failed to parse SMS: {sms_string}") # Use custom logger or app.logger
    return None

# --- Alert Checking Logic ---
def check_meter_alert_status(meter_data_row):
    """
    Checks a single meter's latest data row for alert conditions.
    Returns a string indicating alert type or None.
    """
    if not meter_data_row:
        return None

    status_code = meter_data_row.status_code
    battery_vol_str = meter_data_row.battery_vol
    network_str = meter_data_row.network

    alerts = []

    if status_code in ['FORMAT_WARN', 'DATA_ERR']:
        alerts.append(f"Data Issue ({status_code})")

    try:
        if battery_vol_str:
            battery_mv = int(battery_vol_str)
            if battery_mv < 3500: # Example: 3.5V threshold
                alerts.append("Low Battery")
    except ValueError:
        alerts.append("Invalid Battery Data") # Or handle as DATA_ERR

    try:
        if network_str:
            network_signal = int(network_str)
            if network_signal < 10: # Example: Signal strength threshold
                alerts.append("No/Low Signal")
    except ValueError:
        alerts.append("Invalid Network Data") # Or handle as DATA_ERR
    
    if alerts:
        return ", ".join(alerts) # Return a comma-separated string of alerts
    return None

# --- API Endpoints ---
@app.route('/api/submit-data', methods=['POST'])
@require_api_key # Apply the decorator here
def submit_data():
    data = request.json
    if not data or 'sms_payload' not in data:
        return jsonify({"error": "Missing sms_payload"}), 400

    raw_sms = data['sms_payload']
    parsed_data = parse_sms_data(raw_sms)

    if not parsed_data:
        # Logging is now handled within parse_sms_data
        return jsonify({"error": "Invalid SMS format"}), 400

    conn, cursor = None, None
    try:
        conn, cursor = get_db_cursor()
        sql = """
            INSERT INTO dbo.meter_data (timestamp, MID, status_code, battery_vol, network, WH)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        # Server timestamp for accuracy
        current_timestamp = datetime.datetime.utcnow()
        
        cursor.execute(sql, 
                       current_timestamp,
                       parsed_data['MID'], 
                       parsed_data['status_code'],
                       parsed_data['battery_vol'], 
                       parsed_data['network'], 
                       parsed_data['WH'])
        conn.commit()
        logger.info(f"Data submitted successfully for MID: {parsed_data['MID']}")
        return jsonify({"message": "Data submitted successfully", "MID": parsed_data['MID']}), 201
    except pyodbc.Error as ex:
        sqlstate = ex.args[0]
        logger.error(f"Database Error submitting data: {sqlstate} - {ex}", exc_info=True)
        return jsonify({"error": "Database error", "details": str(ex)}), 500
    except Exception as e:
        logger.error(f"General Error submitting data: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/api/meters', methods=['GET'])
def get_meters():
    conn, cursor = None, None
    try:
        conn, cursor = get_db_cursor()
        # Get distinct meter IDs and their latest timestamp and liter reading
        # This query is for SQL Server
        sql = """
            WITH RankedData AS (
                SELECT
                    MID,
                    WH,
                    timestamp,
                    status_code,
                    battery_vol,
                    network,
                    ROW_NUMBER() OVER (PARTITION BY MID ORDER BY timestamp DESC) as rn
                FROM dbo.meter_data
            )
            SELECT MID, WH, timestamp, status_code, battery_vol, network
            FROM RankedData
            WHERE rn = 1
            ORDER BY MID;
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        meters = []
        for row in rows:
            alert_status = check_meter_alert_status(row) # Get alert status
            meters.append({
                "MID": row.MID,
                "WH": row.WH, # Ensure this matches the database column name and frontend expectation
                "timestamp": row.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC') if row.timestamp else None,
                "status_code": row.status_code, # Original status code from parsing
                "battery_vol": row.battery_vol,
                "network": row.network,
                "alert_status": alert_status # Add the new alert status field
            })
        return jsonify(meters)
    except Exception as e:
        logger.error(f"Error fetching meters: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch meters", "details": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/api/meter/<string:meter_id>/history', methods=['GET'])
def get_meter_history(meter_id):
    # Add optional query parameters for time range, e.g., ?days=7
    days_back = request.args.get('days', default=30, type=int)
    
    conn, cursor = None, None
    try:
        conn, cursor = get_db_cursor()
        # Ensure timestamp is indexed for performance
        sql = """
                   SELECT timestamp, WH, battery_vol, network, status_code
     FROM dbo.meter_data
            WHERE MID = ? AND timestamp >= DATEADD(day, -?, GETUTCDATE())
            ORDER BY timestamp ASC;
        """
        cursor.execute(sql, meter_id, days_back)
        rows = cursor.fetchall()
        history = []
        for row in rows:
            history.append({
                "timestamp": row.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC'),
                "WH": row.WH,
                "battery_vol": row.battery_vol,
                "network": row.network,
                "status_code": row.status_code
            })
        return jsonify(history)
    except Exception as e:
        logger.error(f"Error fetching history for meter {meter_id}: {e}", exc_info=True)
        return jsonify({"error": f"Failed to fetch history for meter {meter_id}", "details": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) # Run on all available IPs
    # If using Flask's built-in server for development, its own logger will handle output.
    # If you added a file_handler to app.logger, it will also log to file.
    logger.info("Starting Water Meter API...")